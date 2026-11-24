"""Drop ON DELETE CASCADE from tenant_users foreign keys

Revision ID: 8a9b0c1d2e3f
Revises: 7f8a9b2c3d4e
Create Date: 2026-11-24

Deletion policy: the platform uses soft-delete (`deleted_at`) and business
logic; physical deletes must never cascade. The original auth baseline created
``tenant_users.user_id`` / ``tenant_id`` with ``ON DELETE CASCADE``. This
revision recreates both FKs without it, so a physical delete that violates a
dependency fails and can be repaired instead of silently deleting rows.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '8a9b0c1d2e3f'
down_revision: Union[str, Sequence[str]] = '7f8a9b2c3d4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Recreate tenant_users FKs without ON DELETE CASCADE."""
    op.drop_constraint(
        'tenant_users_user_id_fkey', 'tenant_users', type_='foreignkey'
    )
    op.create_foreign_key(
        'tenant_users_user_id_fkey',
        'tenant_users',
        'users',
        ['user_id'],
        ['id'],
    )
    op.drop_constraint(
        'tenant_users_tenant_id_fkey', 'tenant_users', type_='foreignkey'
    )
    op.create_foreign_key(
        'tenant_users_tenant_id_fkey',
        'tenant_users',
        'tenants',
        ['tenant_id'],
        ['id'],
    )


def downgrade() -> None:
    """Not supported: restoring cascading deletes is intentionally avoided."""
    raise NotImplementedError(
        "Downgrade not supported: ON DELETE CASCADE is not restored by policy."
    )
