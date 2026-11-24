"""Convert tenant RBAC audit columns to UUID on already-migrated databases

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-11-24

``a1b2c3d4e5f6`` now converts ``created_by``/``updated_by`` for the nine RBAC
tables, but databases migrated with tenants2fast 0.10.0/0.10.1 already have
that revision stamped and never re-run its body. Their audit columns stayed
``bigint`` while ``AuditTimestampMixin`` writes UUIDs, so the RBAC seeder fails
with "column created_by is of type bigint but expression is of type uuid".

This revision converts any remaining integer audit column to UUID. It is a
no-op on fresh databases (a1b2 already converted them).

Offline-safe: the DO block checks ``information_schema`` at execution time.
"""

from typing import Sequence, Union

from alembic import op

revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, Sequence[str]] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_RBAC_TABLES = (
    'categories',
    'roles',
    'routes',
    'users',
    'permissions',
    'role_users',
    'permission_roles',
    'permission_routes',
    'permission_users',
)


def upgrade() -> None:
    """Convert created_by/updated_by to UUID where still integer."""
    op.execute(
        """
        DO $$
        DECLARE r record;
        BEGIN
            FOR r IN
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND column_name IN ('created_by', 'updated_by')
                  AND data_type IN ('integer', 'bigint', 'smallint')
                  AND table_name IN (
                      'categories', 'roles', 'routes', 'users', 'permissions',
                      'role_users', 'permission_roles', 'permission_routes',
                      'permission_users'
                  )
            LOOP
                EXECUTE format(
                    'ALTER TABLE %I ALTER COLUMN %I TYPE uuid '
                    'USING gen_random_uuid()',
                    r.table_name,
                    r.column_name
                );
            END LOOP;
        END $$;
        """
    )


def downgrade() -> None:
    """Not supported: audit integer values are not recoverable."""
    raise NotImplementedError(
        "Downgrade not supported: restoring bigint audit columns is destructive."
    )
