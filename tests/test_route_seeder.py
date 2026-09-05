"""
Tests for the TENANT route+link seeder (tenants2fast-fastapi).

RBAC standardization D2: the TENANT route/permission_routes/role inserter
lives HERE (tenants2fast) so a client manifest of guarded tenant routes is
seeded into each per-tenant DB idempotently (insert-if-missing by natural
key; the tenant Route key is ``path``+``method``).

TENANT rules:
- cover-all routes (no explicit roles) default to the tenant OWNER role.
- explicit roles are honored when declared.
- profile-aware (dev/prod): PROD must not receive dev-only tenant routes.

Run with:
  cd /Volumes/Desarrollo/Repos/Github/tenants2fast-fastapi \
    && uv run --no-sync pytest tests/test_route_seeder.py -v
"""

from __future__ import annotations

import pytest
from sqlalchemy import BigInteger
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlmodel.ext.asyncio.session import AsyncSession

from tenant2fast_fastapi.models.bases import tenant_metadata


@compiles(BigInteger, "sqlite")
def _compile_bigint_sqlite(type_, compiler, **kw):
    return "INTEGER"


DB_URL = "sqlite+aiosqlite:///:memory:"


async def _tenant_engine():
    """Tenant SQLite engine: only tenant_metadata (no auth routes conflict)."""
    from tenant2fast_fastapi.utils.models_loader import import_tenant_models

    import_tenant_models()
    engine = create_async_engine(DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(tenant_metadata.create_all)
    return engine


def _spec(method, path, permission, roles, profile):
    from tenant2fast_fastapi.services.route_seeder import RouteSpec

    return RouteSpec(method=method, path=path, permission=permission, roles=roles, profile=profile)


@pytest.mark.asyncio
async def test_seed_tenant_routes_cover_all_defaults_to_owner():
    """Tenant cover-all route (no roles) -> OWNER role, idempotent."""
    from sqlalchemy import text

    from tenant2fast_fastapi.services.route_seeder import seed_tenant_routes

    engine = await _tenant_engine()
    async with AsyncSession(engine) as session:
        manifest = [
            _spec("POST", "/tenant/users/", None, [], {"dev", "prod"}),
        ]
        summary = await seed_tenant_routes(session, manifest, "dev")
        await session.commit()

        async with engine.connect() as conn:
            routes = (await conn.execute(text("SELECT path, method FROM routes"))).all()
            roles = (await conn.execute(text("SELECT name FROM roles"))).all()

        assert [(r[0], r[1]) for r in routes] == [("/tenant/users/", "POST")]
        # Cover-all defaulted to the OWNER role
        assert [r[0] for r in roles] == ["OWNER"]
        assert "OWNER" in [r[0] for r in roles]
        assert summary["tenant_routes"] == 1

        # --- Idempotency: second call does not duplicate ---
        await seed_tenant_routes(session, manifest, "dev")
        await session.commit()
        async with engine.connect() as conn:
            n_routes = (await conn.execute(text("SELECT COUNT(*) FROM routes"))).scalar()
            n_roles = (await conn.execute(text("SELECT COUNT(*) FROM roles"))).scalar()
        assert n_routes == 1
        assert n_roles == 1
    await engine.dispose()


@pytest.mark.asyncio
async def test_seed_tenant_routes_explicit_roles():
    """Tenant route with explicit roles -> those roles created (not OWNER)."""
    from sqlalchemy import text

    from tenant2fast_fastapi.services.route_seeder import seed_tenant_routes

    engine = await _tenant_engine()
    async with AsyncSession(engine) as session:
        manifest = [
            _spec("GET", "/tenant/reports", None, ["Analyst"], {"dev", "prod"}),
        ]
        summary = await seed_tenant_routes(session, manifest, "dev")
        await session.commit()

        async with engine.connect() as conn:
            roles = (await conn.execute(text("SELECT name FROM roles"))).all()
        assert [r[0] for r in roles] == ["Analyst"]
        assert summary["tenant_roles"] == 1
    await engine.dispose()


@pytest.mark.asyncio
async def test_seed_tenant_routes_prod_excludes_dev_only():
    """prod must not receive dev-only tenant routes (profile-aware)."""
    from sqlalchemy import text

    from tenant2fast_fastapi.services.route_seeder import seed_tenant_routes

    engine = await _tenant_engine()
    async with AsyncSession(engine) as session:
        manifest = [
            _spec("DELETE", "/tenant/debug/cache", None, [], {"dev"}),
            _spec("GET", "/tenant/users/", None, [], {"dev", "prod"}),
        ]
        summary = await seed_tenant_routes(session, manifest, "prod")
        await session.commit()

        async with engine.connect() as conn:
            rows = (await conn.execute(text("SELECT path, method FROM routes"))).all()
        paths = {(r[0], r[1]) for r in rows}

        assert ("/tenant/debug/cache", "DELETE") not in paths
        assert ("/tenant/users/", "GET") in paths
        assert summary["tenant_routes"] == 1
    await engine.dispose()


@pytest.mark.asyncio
async def test_seed_tenant_routes_permission_link():
    """Explicit permission on a tenant route -> permission + permission_routes row."""
    from sqlalchemy import text

    from tenant2fast_fastapi.services.route_seeder import seed_tenant_routes

    engine = await _tenant_engine()
    async with AsyncSession(engine) as session:
        manifest = [
            _spec("PATCH", "/tenant/users/{user_id}", "user_edit", ["OWNER"], {"dev", "prod"}),
        ]
        summary = await seed_tenant_routes(session, manifest, "dev")
        await session.commit()

        async with engine.connect() as conn:
            perms = (await conn.execute(text("SELECT name FROM permissions"))).all()
            links = (await conn.execute(text("SELECT COUNT(*) FROM permission_routes"))).scalar()

        assert [p[0] for p in perms] == ["user_edit"]
        assert links == 1
        assert summary["tenant_links"] == 1
    await engine.dispose()
