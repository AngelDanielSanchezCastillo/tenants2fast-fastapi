"""uuid_v7 + soft-delete for tenant RBAC tables

Revision ID: a1b2c3d4e5f6
Revises: 0001
Create Date: 2026-11-23

Migrates every tenant-plane table from BigInteger to UUID v7 and replaces
is_active with SoftDeleteMixin (deleted_at + deleted_by):

- categories, roles, routes, users, permissions (core)
- role_users, permission_roles, permission_routes, permission_users (assignments)

Order: add soft-delete columns → drop is_active → migrate PKs → migrate FKs.
"""
from typing import Sequence, Union

from alembic import op

from pgsqlasync2fast_fastapi.migration_helpers import (
    add_soft_delete_columns_alembic,
    migrate_fk_to_uuid_alembic,
    migrate_pk_to_uuid_alembic,
)


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str]] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Tables that carry is_active (replaced by soft-delete).
_IS_ACTIVE_TABLES = ("users", "roles", "permissions")

# All tenant RBAC tables (core + assignments).
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


def upgrade() -> None:
    """Upgrade schema: bigint → UUID + soft-delete."""
    # 1. Add soft-delete columns to every table.
    for table in _ALL_TABLES:
        add_soft_delete_columns_alembic(op, table)

    # 2. Drop is_active from tables that had it (replaced by soft-delete).
    for table in _IS_ACTIVE_TABLES:
        op.drop_column(table, 'is_active')

    # 3. Migrate PKs for all tables (FKs temporarily broken).
    for table in _ALL_TABLES:
        migrate_pk_to_uuid_alembic(op, table)

    # 4. Migrate FKs in assignment tables (now that referenced PKs are UUID).
    # role_users: user_id → users.id, role_id → roles.id
    migrate_fk_to_uuid_alembic(op, 'role_users', 'user_id', 'users')
    migrate_fk_to_uuid_alembic(op, 'role_users', 'role_id', 'roles')

    # permission_roles: role_id → roles.id, permission_id → permissions.id
    migrate_fk_to_uuid_alembic(op, 'permission_roles', 'role_id', 'roles')
    migrate_fk_to_uuid_alembic(op, 'permission_roles', 'permission_id', 'permissions')

    # permission_routes: permission_id → permissions.id, route_id → routes.id
    migrate_fk_to_uuid_alembic(op, 'permission_routes', 'permission_id', 'permissions')
    migrate_fk_to_uuid_alembic(op, 'permission_routes', 'route_id', 'routes')

    # permission_users: user_id → users.id, permission_id → permissions.id
    migrate_fk_to_uuid_alembic(op, 'permission_users', 'user_id', 'users')
    migrate_fk_to_uuid_alembic(op, 'permission_users', 'permission_id', 'permissions')

    # permissions: permission_category_id → categories.id
    migrate_fk_to_uuid_alembic(op, 'permissions', 'permission_category_id', 'categories')


def downgrade() -> None:
    """Downgrade schema: UUID → bigint, remove soft-delete columns."""
    # 1. Re-add is_active for tables that had it.
    for table in _IS_ACTIVE_TABLES:
        op.add_column(
            table,
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        )

    # 2. Drop soft-delete columns (reverse order of tables).
    for table in reversed(_ALL_TABLES):
        op.drop_column(table, 'deleted_by')
        op.drop_column(table, 'deleted_at')
