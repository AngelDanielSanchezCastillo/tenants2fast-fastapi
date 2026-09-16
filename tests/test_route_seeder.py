"""
Tests for the TENANT route+link seeder (tenants2fast-fastapi).

RBAC standardization D2: the TENANT route/permission_routes/role inserter
lives HERE (tenants2fast) so a client manifest of guarded tenant routes is
seeded into each per-tenant DB idempotently (insert-if-missing by natural
key; the tenant Route key is ``path``+``method``).

TENANT rules:
- cover-all routes (no explicit roles) default to the tenant Owner role.
- explicit roles are honored when declared.
- profile-aware (dev/prod): PROD must not receive dev-only tenant routes.
- routes with a `permission` create a `PermissionRole` grant per effective role
  (declared roles, or Owner for cover-all); idempotent via insert-if-missing.

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
    """Tenant cover-all route (no roles) -> Owner role, idempotent."""
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
        # Cover-all defaulted to the Owner role (dedupe: no legacy "OWNER")
        assert [r[0] for r in roles] == ["Owner"]
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
    """Tenant route with explicit roles -> those roles created (not Owner)."""
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
            _spec("PATCH", "/tenant/users/{user_id}", "user_edit", ["Owner"], {"dev", "prod"}),
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


@pytest.mark.asyncio
async def test_seed_tenant_routes_creates_role_permission_grants():
    """Explicit roles + permission -> one PermissionRole grant per declared role."""
    from sqlalchemy import text

    from tenant2fast_fastapi.services.route_seeder import seed_tenant_routes

    engine = await _tenant_engine()
    async with AsyncSession(engine) as session:
        manifest = [
            _spec("GET", "/tenant/products", "products:read", ["Manager", "Member"], {"dev", "prod"}),
        ]
        summary = await seed_tenant_routes(session, manifest, "dev")
        await session.commit()

        async with engine.connect() as conn:
            grants = (
                await conn.execute(
                    text(
                        "SELECT r.name, p.name FROM permission_roles pr "
                        "JOIN roles r ON r.id = pr.role_id "
                        "JOIN permissions p ON p.id = pr.permission_id"
                    )
                )
            ).all()

        assert {tuple(g) for g in grants} == {
            ("Manager", "products:read"),
            ("Member", "products:read"),
        }
        assert summary["tenant_grants"] == 2
    await engine.dispose()


@pytest.mark.asyncio
async def test_seed_tenant_routes_owner_cover_all_grant():
    """Cover-all route (roles=[]) + permission -> Owner PermissionRole grant."""
    from sqlalchemy import text

    from tenant2fast_fastapi.services.route_seeder import seed_tenant_routes

    engine = await _tenant_engine()
    async with AsyncSession(engine) as session:
        manifest = [
            _spec("GET", "/tenant/clients", "clients:read", [], {"dev", "prod"}),
        ]
        summary = await seed_tenant_routes(session, manifest, "dev")
        await session.commit()

        async with engine.connect() as conn:
            grants = (
                await conn.execute(
                    text(
                        "SELECT r.name, p.name FROM permission_roles pr "
                        "JOIN roles r ON r.id = pr.role_id "
                        "JOIN permissions p ON p.id = pr.permission_id"
                    )
                )
            ).all()

        assert [tuple(g) for g in grants] == [("Owner", "clients:read")]
        assert summary["tenant_grants"] == 1
    await engine.dispose()


@pytest.mark.asyncio
async def test_seed_tenant_routes_grant_idempotent_on_duplicate_seed():
    """Duplicate seed -> exactly 1 PermissionRole row per role/permission pair."""
    from sqlalchemy import text

    from tenant2fast_fastapi.services.route_seeder import seed_tenant_routes

    engine = await _tenant_engine()
    async with AsyncSession(engine) as session:
        manifest = [
            _spec("GET", "/tenant/products", "products:read", ["Manager"], {"dev", "prod"}),
        ]
        await seed_tenant_routes(session, manifest, "dev")
        await session.commit()
        await seed_tenant_routes(session, manifest, "dev")
        await session.commit()

        async with engine.connect() as conn:
            n_grants = (await conn.execute(text("SELECT COUNT(*) FROM permission_roles"))).scalar()

        assert n_grants == 1
    await engine.dispose()


@pytest.mark.asyncio
async def test_seed_tenant_routes_no_permission_creates_no_grants():
    """Route without permission -> roles created but no PermissionRole rows."""
    from sqlalchemy import text

    from tenant2fast_fastapi.services.route_seeder import seed_tenant_routes

    engine = await _tenant_engine()
    async with AsyncSession(engine) as session:
        manifest = [
            _spec("POST", "/tenant/users/", None, ["Owner"], {"dev", "prod"}),
        ]
        summary = await seed_tenant_routes(session, manifest, "dev")
        await session.commit()

        async with engine.connect() as conn:
            roles = (await conn.execute(text("SELECT name FROM roles"))).all()
            n_grants = (await conn.execute(text("SELECT COUNT(*) FROM permission_roles"))).scalar()

        assert [r[0] for r in roles] == ["Owner"]
        assert n_grants == 0
        assert summary["tenant_grants"] == 0
    await engine.dispose()


@pytest.mark.asyncio
async def test_seed_tenant_routes_dev_only_route_skipped_in_prod_creates_no_grants():
    """prod skips dev-only routes -> their permission and grants are never seeded."""
    from sqlalchemy import text

    from tenant2fast_fastapi.services.route_seeder import seed_tenant_routes

    engine = await _tenant_engine()
    async with AsyncSession(engine) as session:
        manifest = [
            _spec("DELETE", "/tenant/debug/cache", "debug:purge", [], {"dev"}),
            _spec("GET", "/tenant/clients", "clients:read", ["Member"], {"dev", "prod"}),
        ]
        summary = await seed_tenant_routes(session, manifest, "prod")
        await session.commit()

        async with engine.connect() as conn:
            perms = (await conn.execute(text("SELECT name FROM permissions"))).all()
            grants = (
                await conn.execute(
                    text(
                        "SELECT r.name, p.name FROM permission_roles pr "
                        "JOIN roles r ON r.id = pr.role_id "
                        "JOIN permissions p ON p.id = pr.permission_id"
                    )
                )
            ).all()

        assert [p[0] for p in perms] == ["clients:read"]
        assert [tuple(g) for g in grants] == [("Member", "clients:read")]
        assert summary["tenant_grants"] == 1
    await engine.dispose()


def test_permission_role_unique_constraint_declared():
    """PermissionRole declares uq_permission_roles_role_permission on (role_id, permission_id)."""
    from tenant2fast_fastapi.models.assignments_model import (
        PermissionRole,  # noqa: F401  (registers model)
    )
    from tenant2fast_fastapi.models.bases import tenant_metadata

    table = tenant_metadata.tables["permission_roles"]
    constraints = [
        c for c in table.constraints if getattr(c, "name", None) == "uq_permission_roles_role_permission"
    ]
    assert len(constraints) == 1
    assert {col.name for col in constraints[0].columns} == {"role_id", "permission_id"}
