"""uuid_v7 + soft-delete for tenants and tenant_users

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-23

Migrates:
- tenants: id BigInteger → UUID, is_active → deleted_at + deleted_by
- tenant_users: id BigInteger → UUID, user_id/tenant_id BigInteger → UUID,
  add deleted_at + deleted_by

Order: soft-delete columns → drop is_active → migrate PKs → migrate FKs.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

from pgsqlasync2fast_fastapi.migration_helpers import (
    migrate_fk_to_uuid,
    migrate_pk_to_uuid,
)
from ..helpers import add_soft_delete_columns


# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, Sequence[str]] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: bigint → UUID + soft-delete."""
    # 1. Add soft-delete columns (before any PK/FK changes)
    add_soft_delete_columns('tenants')
    add_soft_delete_columns('tenant_users')

    # 2. Drop is_active from tenants (replaced by soft-delete)
    op.drop_column('tenants', 'is_active')

    # 3. Migrate PKs first (FKs temporarily broken, but that's OK)
    migrate_pk_to_uuid('tenants')
    migrate_pk_to_uuid('tenant_users')

    # 4. Migrate FKs (now that referenced PKs are UUID)
    migrate_fk_to_uuid('tenant_users', 'user_id', 'users')
    migrate_fk_to_uuid('tenant_users', 'tenant_id', 'tenants')


def downgrade() -> None:
    """Downgrade schema: UUID → bigint, remove soft-delete columns."""
    # Re-add is_active
    op.add_column(
        'tenants',
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    # Downgrade PKs back to BigInteger (simplified — data loss expected)
    op.drop_column('tenant_users', 'id')
    op.add_column(
        'tenant_users',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
    )

    op.drop_column('tenants', 'id')
    op.add_column(
        'tenants',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
    )

    # Downgrade FKs back to BigInteger (simplified)
    op.drop_column('tenant_users', 'tenant_id')
    op.add_column(
        'tenant_users',
        sa.Column('tenant_id', sa.BigInteger(), sa.ForeignKey('tenants.id', ondelete='CASCADE')),
    )

    op.drop_column('tenant_users', 'user_id')
    op.add_column(
        'tenant_users',
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE')),
    )

    # Remove soft-delete columns
    op.drop_column('tenant_users', 'deleted_by')
    op.drop_column('tenant_users', 'deleted_at')
    op.drop_column('tenants', 'deleted_by')
    op.drop_column('tenants', 'deleted_at')
