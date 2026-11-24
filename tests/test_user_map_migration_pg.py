"""Cross-package PostgreSQL regression for the auth-lane user-id map.

The AUTH lane is composed of three chains that each own part of the schema:

    oauth2fast          -> users, oauth__refresh_tokens
    permissions2fast    -> roles, role_users, ...
    tenants2fast-auth   -> tenants, tenant_users

``role_users.user_id`` and ``tenant_users.user_id`` reference ``users.id``.
Migrating ``users`` to UUID requires dropping those external FKs, and the old
integer values must still map to the same UUIDs. ``oauth2fast`` leaves a
persistent ``_uuid_migration_user_map`` that the siblings consume; the last
chain drops it.

This test builds the integer baseline, seeds related rows, upgrades the three
chains in lane order and asserts the relationships survived.

Requires a disposable PostgreSQL database:

    PG_TEST_URL=postgresql+asyncpg://user:pass@host:5432/db \\
        uv run pytest tests/test_user_map_migration_pg.py -v

The schema in that database is dropped and recreated.
"""

from __future__ import annotations

import asyncio
import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

PG_URL = os.getenv("PG_TEST_URL")

pytestmark = pytest.mark.skipif(
    not PG_URL, reason="PG_TEST_URL not set (disposable PostgreSQL required)"
)

OAUTH_CHAIN = ("oauth2fast_fastapi:migrations/oauth", "alembic_version_oauth")
PERMISSIONS_CHAIN = (
    "permissions2fast_fastapi:migrations/permissions-global",
    "alembic_version_permissions",
)
TENANT_AUTH_CHAIN = (
    "tenant2fast_fastapi:migrations/tenant2fast-auth",
    "alembic_version_tenant_auth",
)


def _config(chain: tuple[str, str]) -> Config:
    script_location, version_table = chain
    cfg = Config()
    cfg.set_main_option("script_location", script_location)
    cfg.set_main_option("sqlalchemy.url", PG_URL)
    cfg.set_main_option("version_table", version_table)
    return cfg


async def _reset_schema() -> None:
    engine = create_async_engine(PG_URL)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("DROP SCHEMA public CASCADE"))
            await conn.execute(text("CREATE SCHEMA public"))
    finally:
        await engine.dispose()


async def _seed() -> None:
    engine = create_async_engine(PG_URL)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO users "
                    "(id, created_at, updated_at, name, email, password, is_verified) "
                    "VALUES (1, now(), now(), 'Map User', 'map@example.com', 'x', true)"
                )
            )
            await conn.execute(
                text(
                    "INSERT INTO tenants "
                    "(id, created_at, updated_at, name, slug, database_name, is_active) "
                    "VALUES (1, now(), now(), 'Map Tenant', 'map-tenant', 'map_tenant', true)"
                )
            )
            await conn.execute(
                text(
                    "INSERT INTO tenant_users "
                    "(id, created_at, updated_at, user_id, tenant_id) "
                    "VALUES (1, now(), now(), 1, 1)"
                )
            )
            await conn.execute(
                text(
                    "INSERT INTO roles "
                    "(id, created_at, updated_at, name, is_active) "
                    "VALUES (1, now(), now(), 'map-role', true)"
                )
            )
            await conn.execute(
                text(
                    "INSERT INTO role_users "
                    "(id, created_at, updated_at, user_id, role_id) "
                    "VALUES (1, now(), now(), 1, 1)"
                )
            )
    finally:
        await engine.dispose()


async def _assert_preserved() -> None:
    engine = create_async_engine(PG_URL)
    try:
        async with engine.connect() as conn:
            user_id = (
                await conn.execute(text("SELECT id FROM users WHERE id = id"))
            ).scalar_one()
            tenant_user_id = (
                await conn.execute(text("SELECT user_id FROM tenant_users"))
            ).scalar_one()
            role_user_id = (
                await conn.execute(text("SELECT user_id FROM role_users"))
            ).scalar_one()

            assert tenant_user_id == user_id
            assert role_user_id == user_id

            user_id_type = (
                await conn.execute(
                    text(
                        "SELECT data_type FROM information_schema.columns "
                        "WHERE table_name = 'users' AND column_name = 'id'"
                    )
                )
            ).scalar_one()
            assert user_id_type == "uuid"

            joins = (
                await conn.execute(
                    text(
                        "SELECT "
                        "(SELECT count(*) FROM tenant_users tu JOIN users u ON u.id = tu.user_id), "
                        "(SELECT count(*) FROM role_users ru JOIN users u ON u.id = ru.user_id), "
                        "(SELECT count(*) FROM tenant_users tu JOIN tenants t ON t.id = tu.tenant_id)"
                    )
                )
            ).one()
            assert joins == (1, 1, 1)

            map_table = (
                await conn.execute(
                    text("SELECT to_regclass('_uuid_migration_user_map')")
                )
            ).scalar_one()
            assert map_table is None

            cascade_count = (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM pg_constraint "
                        "WHERE contype = 'f' AND confdeltype = 'c'"
                    )
                )
            ).scalar_one()
            assert cascade_count == 0
    finally:
        await engine.dispose()


def test_user_ids_preserved_across_auth_lane() -> None:
    asyncio.run(_reset_schema())

    # Integer baseline: oauth before its UUID migration, the other two at 0001.
    command.upgrade(_config(OAUTH_CHAIN), "45b786644a86")
    command.upgrade(_config(PERMISSIONS_CHAIN), "0001")
    command.upgrade(_config(TENANT_AUTH_CHAIN), "0001")

    asyncio.run(_seed())

    # Lane order: oauth -> permissions -> tenant2fast-auth.
    command.upgrade(_config(OAUTH_CHAIN), "head")
    command.upgrade(_config(PERMISSIONS_CHAIN), "head")
    command.upgrade(_config(TENANT_AUTH_CHAIN), "head")

    asyncio.run(_assert_preserved())
