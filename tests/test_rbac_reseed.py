"""
Tests for the RBAC re-seed orchestration service (tenants2fast-fastapi).

``reseed_all_rbac`` is the reusable platform entrypoint for multi-tenant
deployments: it seeds GLOBAL routes on the auth DB (permissions2fast) and, for
each tenant, runs the RBAC seeder + TENANT route seeding (tenants2fast). The
app used to own this orchestration; it now lives here so any multi-tenant
client can call it with its own declarative manifests.

Verified with SQLite in-memory engines + monkeypatched connection manager and
tenant RBAC engine (the per-tenant RBAC engine internals are covered by
test_seeder.py/test_route_seeder.py; here we prove the ORCHESTRATION):
- GLOBAL manifest routes land in the auth DB via ``seed_global_routes``
- every active tenant gets ``seed()`` + ``seed_tenant_routes()``
- ``active_only=True`` skips inactive tenants
- a failing tenant does not block the others (non-fatal)

Run with:
  cd /Volumes/Desarrollo/Repos/Github/tenants2fast-fastapi \
    && uv run --no-sync pytest tests/test_rbac_reseed.py -v
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.types import BigInteger
from sqlmodel.ext.asyncio.session import AsyncSession

from oauth2fast_fastapi.models.bases import AuthModel


@compiles(BigInteger, "sqlite")
def _compile_bigint_sqlite(type_, compiler, **kw):
    return "INTEGER"


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return compiler.visit_JSON(SQLiteJSON(), **kw)


DB_URL = "sqlite+aiosqlite:///:memory:"


class _FakeManager:
    """Minimal stand-in for pgsqlasync2fast's DatabaseManager."""

    def __init__(self, auth_engine):
        self._auth_engine = auth_engine

    def get_engine(self, name):
        return self._auth_engine


async def _auth_engine():
    """Auth SQLite engine: AuthModel metadata (incl. permissions2fast routes)."""
    from permissions2fast_fastapi.models.permission_category_model import (  # noqa: F401
        PermissionCategory,
    )
    from permissions2fast_fastapi.models.permission_model import Permission  # noqa: F401
    from permissions2fast_fastapi.models.permission_route_model import (  # noqa: F401
        PermissionRoute,
    )
    from permissions2fast_fastapi.models.role_model import Role  # noqa: F401
    from permissions2fast_fastapi.models.role_user_model import RoleUser  # noqa: F401
    from permissions2fast_fastapi.models.route_model import Route  # noqa: F401
    from tenant2fast_fastapi.models.tenant_model import Tenant  # noqa: F401

    engine = create_async_engine(DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(AuthModel.metadata.create_all)
    return engine


async def _tenant_engine():
    """Tenant SQLite engine: only tenant_metadata (no auth routes conflict)."""
    from tenant2fast_fastapi.models.bases import tenant_metadata
    from tenant2fast_fastapi.utils.models_loader import import_tenant_models

    import_tenant_models()
    engine = create_async_engine(DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(tenant_metadata.create_all)
    return engine


def _tenant_session_factory(tenant_engine):
    """Return an async get_tenant_session stand-in bound to ONE SQLite engine."""

    async def _get_tenant_session(tenant_id):
        return AsyncSession(tenant_engine, expire_on_commit=False)

    return _get_tenant_session


def _seed_fake(*, fail_tenant_id: int | None = None):
    async def fake_seed(profile, tenant_id):
        if tenant_id == fail_tenant_id:
            raise RuntimeError("boom")
        return {"tables_seeded": 1, "rows_seeded": 3, "errors": []}

    return fake_seed


def _manifests():
    """One GLOBAL spec + one TENANT spec (same shapes as client manifests)."""
    from permissions2fast_fastapi.services.route_seeder import (
        RouteSpec as GlobalRouteSpec,
    )
    from tenant2fast_fastapi.services.route_seeder import RouteSpec as TenantRouteSpec

    global_manifest = [
        GlobalRouteSpec(
            method="GET",
            path="/tenants/control",
            permission="tenants_control",
            roles=["Admin"],
            profile={"dev", "prod"},
        )
    ]
    tenant_manifest = [
        TenantRouteSpec(
            method="POST",
            path="/tenant/users/",
            permission=None,
            roles=[],
            profile={"dev", "prod"},
        )
    ]
    return global_manifest, tenant_manifest


def _patch_infra(monkeypatch, auth_engine, tenant_engine, fake_seed):
    """Point the reseed service at SQLite engines + a fake per-tenant seed()."""
    from pgsqlasync2fast_fastapi import connection as pgsql_connection
    from tenant2fast_fastapi.services import tenant_rbac_seeder as seeder_mod

    monkeypatch.setattr(
        pgsql_connection, "get_manager", lambda: _FakeManager(auth_engine)
    )
    monkeypatch.setattr(
        seeder_mod, "get_tenant_session", _tenant_session_factory(tenant_engine)
    )
    monkeypatch.setattr(seeder_mod, "seed", fake_seed)


async def _add_tenants(auth_engine, tenants):
    """Insert tenants into the auth DB (interleaved with the config category)."""
    from permissions2fast_fastapi.models.permission_category_model import (
        PermissionCategory,
    )
    from tenant2fast_fastapi.models.tenant_model import Tenant

    async with AsyncSession(auth_engine) as session:
        # The global route permission FK needs a category bucket.
        session.add(PermissionCategory(name="config"))
        for t in tenants:
            session.add(Tenant(**t))
        await session.commit()


@pytest.mark.asyncio
async def test_reseed_all_rbac_seeds_globals_and_active_tenants(monkeypatch):
    """GLOBAL routes + per-tenant seed()/seed_tenant_routes for ACTIVE tenants."""
    auth_engine = await _auth_engine()
    tenant_engine = await _tenant_engine()

    await _add_tenants(
        auth_engine,
        [
            {"name": "Active One", "slug": "active-one", "database_name": "t_1", "is_active": True},
            {"name": "Active Two", "slug": "active-two", "database_name": "t_2", "is_active": True},
            {"name": "Inactive", "slug": "inactive", "database_name": "t_3", "is_active": False},
        ],
    )

    seeded = []
    fake_seed = _seed_fake()

    async def tracked_seed(profile, tenant_id):
        seeded.append(tenant_id)
        return await fake_seed(profile, tenant_id)

    _patch_infra(monkeypatch, auth_engine, tenant_engine, tracked_seed)

    from tenant2fast_fastapi.services.tenant_rbac_seeder import reseed_all_rbac

    global_manifest, tenant_manifest = _manifests()
    summary = await reseed_all_rbac(
        "dev", global_manifest, tenant_manifest, active_only=True
    )

    assert summary["total"] == 2
    assert summary["succeeded"] == 2
    assert summary["failed"] == 0
    assert summary["errors"] == []
    assert summary["global_routes"] == 1
    assert summary["tenant_routes"] == 2  # one per active tenant
    # Only the ACTIVE tenants were seeded (ids 1 and 2; inactive is id 3).
    assert seeded == [1, 2]

    # GLOBAL route landed in the auth DB with its explicit role.
    async with auth_engine.connect() as conn:
        names = [r[0] for r in (await conn.execute(text("SELECT name FROM routes"))).all()]
        role_names = [r[0] for r in (await conn.execute(text("SELECT name FROM roles"))).all()]
    assert names == ["GET /tenants/control"]
    assert "Admin" in role_names

    # TENANT route landed in the shared tenant DB (cover-all -> OWNER).
    async with tenant_engine.connect() as conn:
        paths = [p[0] for p in (await conn.execute(text("SELECT path FROM routes"))).all()]
        tenant_roles = {r[0] for r in (await conn.execute(text("SELECT name FROM roles"))).all()}
    assert paths == ["/tenant/users/"]
    assert "OWNER" in tenant_roles

    await auth_engine.dispose()
    await tenant_engine.dispose()


@pytest.mark.asyncio
async def test_reseed_all_rbac_active_only_false_includes_inactive(monkeypatch):
    """active_only=False seeds EVERY tenant, active or not."""
    auth_engine = await _auth_engine()
    tenant_engine = await _tenant_engine()

    await _add_tenants(
        auth_engine,
        [
            {"name": "Active", "slug": "active", "database_name": "t_1", "is_active": True},
            {"name": "Inactive", "slug": "inactive", "database_name": "t_2", "is_active": False},
        ],
    )

    seeded = []
    fake_seed = _seed_fake()

    async def tracked_seed(profile, tenant_id):
        seeded.append(tenant_id)
        return await fake_seed(profile, tenant_id)

    _patch_infra(monkeypatch, auth_engine, tenant_engine, tracked_seed)

    from tenant2fast_fastapi.services.tenant_rbac_seeder import reseed_all_rbac

    global_manifest, tenant_manifest = _manifests()
    summary = await reseed_all_rbac(
        "dev", global_manifest, tenant_manifest, active_only=False
    )

    assert summary["total"] == 2
    assert summary["succeeded"] == 2
    assert summary["failed"] == 0
    assert seeded == [1, 2]

    await auth_engine.dispose()
    await tenant_engine.dispose()


@pytest.mark.asyncio
async def test_reseed_all_rbac_tenant_failure_is_non_fatal(monkeypatch):
    """A failing tenant is counted as failed; the others still seed."""
    auth_engine = await _auth_engine()
    tenant_engine = await _tenant_engine()

    await _add_tenants(
        auth_engine,
        [
            {"name": "Good", "slug": "good", "database_name": "t_1", "is_active": True},
            {"name": "Bad", "slug": "bad", "database_name": "t_2", "is_active": True},
            {"name": "Also Good", "slug": "also-good", "database_name": "t_3", "is_active": True},
        ],
    )

    # Tenant id=2 fails inside seed(); the other two must still succeed.
    _patch_infra(monkeypatch, auth_engine, tenant_engine, _seed_fake(fail_tenant_id=2))

    from tenant2fast_fastapi.services.tenant_rbac_seeder import reseed_all_rbac

    global_manifest, tenant_manifest = _manifests()
    summary = await reseed_all_rbac(
        "dev", global_manifest, tenant_manifest, active_only=True
    )

    assert summary["total"] == 3
    assert summary["succeeded"] == 2
    assert summary["failed"] == 1
    assert len(summary["errors"]) == 1
    assert "boom" in summary["errors"][0]
    # Only the two successful tenants contributed tenant routes.
    assert summary["tenant_routes"] == 2

    await auth_engine.dispose()
    await tenant_engine.dispose()