"""Rebuild tenant RBAC inbound FKs with ON UPDATE CASCADE (seed-id adoption)."""

from alembic import op

revision = "c1d2e3f4a5b6"
down_revision = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None

RBAC_TABLES = ("categories", "roles", "permissions")


def upgrade() -> None:
    from pgsqlasync2fast_fastapi.migrations.fk_cascade import (
        upgrade_fks_to_on_update_cascade,
    )

    upgrade_fks_to_on_update_cascade(op.get_bind(), RBAC_TABLES)


def downgrade() -> None:
    from pgsqlasync2fast_fastapi.migrations.fk_cascade import (
        downgrade_fks_to_no_action,
    )

    downgrade_fks_to_no_action(op.get_bind(), RBAC_TABLES)
