"""uuid_v7 + soft-delete for tenant RBAC tables

Revision ID: a1b2c3d4e5f6
Revises: 0001
Create Date: 2026-11-23

Migrates every tenant-plane table from BigInteger to UUID v7 and replaces
is_active with SoftDeleteMixin (deleted_at + deleted_by):

- categories, roles, routes, users, permissions (core)
- role_users, permission_roles, permission_routes, permission_users (assignments)

Two-phase, FK-safe:
1. prepare PKs for every table (add id_uuid + backfill, keep old integer id)
2. prepare FKs (add <fk>_uuid + join-backfill via parent.id_uuid / old int id)
3. finalize: drop child FK constraints → swap PKs → swap FKs → recreate
   constraints/indexes → recreate the permission_roles UNIQUE constraint

The tenant-local ``users.auth_user_id`` references the auth ``users.id``
(external DB, already UUID): it is converted with no backfill because the old
integer ids cannot be mapped to the external UUID space.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from pgsqlasync2fast_fastapi.migration_helpers import (
    add_soft_delete_columns_alembic,
    convert_unique_column_to_uuid_alembic,
    dedupe_unique_columns_alembic,
    finalize_uuid_alembic,
    prepare_fk_uuid_alembic,
    prepare_pk_uuid_alembic,
)


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str]] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Tables that carry is_active (replaced by soft-delete).
_IS_ACTIVE_TABLES = ("users", "roles", "permissions")

# All tenant RBAC tables (core + assignments), parents before children.
_ALL_TABLES = (
    "categories",
    "roles",
    "routes",
    "users",
    "permissions",
    "role_users",
    "permission_roles",
    "permission_routes",
    "permission_users",
)

# (child_table, fk_column, parent_table)
_FK_RELATIONS = (
    ("permissions", "permission_category_id", "categories"),
    ("role_users", "user_id", "users"),
    ("role_users", "role_id", "roles"),
    ("permission_roles", "role_id", "roles"),
    ("permission_roles", "permission_id", "permissions"),
    ("permission_routes", "permission_id", "permissions"),
    ("permission_routes", "route_id", "routes"),
    ("permission_users", "user_id", "users"),
    ("permission_users", "permission_id", "permissions"),
)

#: Audit columns are plain nullable columns (not PK/FK, not unique).
_AUDIT_COLUMNS = ("created_by", "updated_by")


def _convert_audit_column(table_name: str, column_name: str) -> None:
    """Convert a nullable, non-unique BigInt audit column to UUID.

    Old integer values point to the auth database's user space and cannot be
    mapped locally; they are dropped (NULL backfill). Offline-safe.
    """
    temp_name = f"{column_name}_uuid"
    index_name = f"ix_{table_name}_{column_name}"

    op.add_column(table_name, sa.Column(temp_name, sa.Uuid(), nullable=True))
    op.drop_index(index_name, table_name=table_name, if_exists=True)
    op.drop_column(table_name, column_name)
    op.alter_column(table_name, temp_name, new_column_name=column_name)
    op.create_index(index_name, table_name, [column_name], unique=False)


def _dedupe_unique_catalogs() -> None:
    """Collapse drifted duplicates in the tenant RBAC unique-name catalogs.

    Duplicate keys behind a valid-looking unique index make the later non-HOT
    ``UPDATE`` (PK swap) abort when PostgreSQL re-validates the index. The
    dependents below are plain FKs, so repointing is unambiguous.

    ``users.auth_user_id`` is intentionally not repaired: it is the external
    identity link; a duplicate there needs a human decision, not a silent merge.
    """
    dedupe_unique_columns_alembic(
        op,
        "categories",
        ("name",),
        index_name="ix_categories_name",
        dependents=[("permissions", "permission_category_id", ())],
    )
    dedupe_unique_columns_alembic(
        op,
        "roles",
        ("name",),
        index_name="ix_roles_name",
        dependents=[
            ("role_users", "role_id", ("user_id",)),
            ("permission_roles", "role_id", ("permission_id",)),
        ],
    )
    dedupe_unique_columns_alembic(
        op,
        "permissions",
        ("name",),
        index_name="ix_permissions_name",
        dependents=[
            ("permission_roles", "permission_id", ("role_id",)),
            ("permission_routes", "permission_id", ("route_id",)),
            ("permission_users", "permission_id", ("user_id",)),
        ],
    )


def upgrade() -> None:
    """Upgrade schema: bigint → UUID + soft-delete (two-phase, FK-safe)."""
    # Duplicate catalog keys make the PK conversion abort on the unique-index
    # re-validation; collapse them first.
    _dedupe_unique_catalogs()

    # --- Soft-delete columns + drop is_active -----------------------------
    for table in _ALL_TABLES:
        add_soft_delete_columns_alembic(op, table)
    for table in _IS_ACTIVE_TABLES:
        op.drop_column(table, 'is_active')

    # --- Audit columns: BigInt -> UUID (nullable, non-unique) -------------
    for table in _ALL_TABLES:
        for column in _AUDIT_COLUMNS:
            _convert_audit_column(table, column)

    # --- Phase 1: prepare PKs and FKs (old integer columns kept) ----------
    for table in _ALL_TABLES:
        prepare_pk_uuid_alembic(op, table)

    # permissions.permission_category_id is nullable in the baseline model.
    prepare_fk_uuid_alembic(
        op, "permissions", "permission_category_id", "categories", nullable=True
    )
    for child, fk_column, parent in _FK_RELATIONS:
        if child == "permissions" and fk_column == "permission_category_id":
            continue  # already prepared (nullable) above
        prepare_fk_uuid_alembic(op, child, fk_column, parent, nullable=False)

    # users.auth_user_id → external auth users.id: no local backfill.
    convert_unique_column_to_uuid_alembic(op, "users", "auth_user_id")

    # --- Phase 2: finalize swap (FK-safe order) ---------------------------
    finalize_uuid_alembic(
        op,
        pk_tables=_ALL_TABLES,
        fk_relations=_FK_RELATIONS,
        unique_constraints=[
            ("permission_roles", "uq_permission_roles_role_permission", ("role_id", "permission_id")),
        ],
    )


def downgrade() -> None:
    """Downgrade schema: not supported (destructive)."""
    raise NotImplementedError(
        "Downgrade not supported: UUID→BigInteger is destructive. "
        "Rebuild the database instead."
    )
