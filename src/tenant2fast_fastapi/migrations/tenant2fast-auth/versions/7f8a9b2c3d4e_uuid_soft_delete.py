"""uuid_v7 + soft-delete for tenants and tenant_users

Revision ID: 7f8a9b2c3d4e
Revises: 0001
Create Date: 2026-11-23

Migrates (two-phase, FK-safe):
- tenants: id BigInteger → UUID, is_active → deleted_at + deleted_by
- tenant_users: id BigInteger → UUID, user_id/tenant_id BigInteger → UUID,
  add deleted_at + deleted_by

Phase 1 (prepare) adds UUID columns and backfills while the old integer
columns still exist. Phase 2 (finalize) drops child FK constraints first, then
swaps PKs, then swaps FKs and recreates constraints/indexes.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

from pgsqlasync2fast_fastapi.migration_helpers import (
    add_soft_delete_columns_alembic,
    finalize_uuid_alembic,
    prepare_fk_uuid_alembic,
    prepare_pk_uuid_alembic,
)


# revision identifiers, used by Alembic.
revision: str = '7f8a9b2c3d4e'
down_revision: Union[str, Sequence[str]] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: bigint → UUID + soft-delete."""
    # --- Soft-delete columns + drop is_active -----------------------------
    add_soft_delete_columns_alembic(op, 'tenants')
    add_soft_delete_columns_alembic(op, 'tenant_users')
    op.drop_column('tenants', 'is_active')

    # --- Phase 1: prepare UUID columns (old integer columns kept) ---------
    prepare_pk_uuid_alembic(op, 'tenants')
    prepare_pk_uuid_alembic(op, 'tenant_users')

    # tenant_users.tenant_id → tenants (same chain): join-backfill works.
    prepare_fk_uuid_alembic(op, 'tenant_users', 'tenant_id', 'tenants', nullable=False)

    # tenant_users.user_id → auth users.id (external): oauth2fast >= 0.8.2
    # drops the FK and leaves a map so old integer ids map to the same UUIDs.
    op.add_column('tenant_users', sa.Column('user_id_uuid', sa.Uuid(), nullable=True))
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('_uuid_migration_user_map') IS NOT NULL THEN
                UPDATE tenant_users AS tu
                SET user_id_uuid = m.new_uuid
                FROM _uuid_migration_user_map AS m
                WHERE m.old_id = tu.user_id
                  AND tu.user_id_uuid IS NULL;
            END IF;
        END $$;
        """
    )

    # --- Phase 2: finalize swap (FK-safe order) ---------------------------
    # user_id is swapped manually: oauth2fast already dropped its FK, so the
    # helper must not try to drop it again.
    finalize_uuid_alembic(
        op,
        pk_tables=['tenants', 'tenant_users'],
        fk_relations=[
            ('tenant_users', 'tenant_id', 'tenants'),
        ],
    )

    # --- tenant_users.user_id: manual swap (external FK already dropped) --
    op.drop_column('tenant_users', 'user_id')
    op.alter_column('tenant_users', 'user_id_uuid', new_column_name='user_id')
    op.create_foreign_key(
        'tenant_users_user_id_fkey',
        'tenant_users',
        'users',
        ['user_id'],
        ['id'],
    )
    op.create_index(
        op.f('ix_tenant_users_user_id'), 'tenant_users', ['user_id'], unique=False
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM tenant_users WHERE user_id IS NULL) THEN
                ALTER TABLE tenant_users ALTER COLUMN user_id SET NOT NULL;
            END IF;
        END $$;
        """
    )

    # The map has been consumed by permissions2fast and this chain: drop it.
    op.execute("DROP TABLE IF EXISTS _uuid_migration_user_map")


def downgrade() -> None:
    """Downgrade schema: UUID → bigint, remove soft-delete columns."""
    raise NotImplementedError(
        "Downgrade not supported: UUID→BigInteger is destructive. "
        "Rebuild the database instead."
    )
