"""
test_tenant_permissions_router.py — HTTP tests for GET /tenants/permissions/.

Regression (staging): the router built PermissionResponse with
``p.permission_category_id`` while the Permission model had no such column
and the response schema declared it as a REQUIRED int → AttributeError/500
on every permission list. After the fix the model field is ``int | None``,
the schema is null-safe, and the endpoint returns 200 with the category
populated when the seed declares it and null otherwise.

Layer: HTTP (router) on an in-memory SQLite tenant DB. The router module is
reloaded under patched dependencies so the real route registration runs
against a fake tenant + a session bound to the SQLite engine.

Run with:
  uv run pytest tests/test_tenant_permissions_router.py -v
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from tenant2fast_fastapi.utils.models_loader import import_tenant_models
from tenant2fast_fastapi.models.bases import tenant_metadata
from tenant2fast_fastapi.models.permission_model import Permission  # noqa: F401
from tenant2fast_fastapi.services.tenant_rbac_seeder import _seed_table_idempotent


async def _tenant_engine():
    """Tenant SQLite engine with the tenant RBAC schema only."""
    import_tenant_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(tenant_metadata.create_all)
    return engine


def _session_factory(engine):
    """Return a get_tenant_session stand-in bound to ONE SQLite engine."""

    async def _get_tenant_session(tenant_id):
        return AsyncSession(engine, expire_on_commit=False)

    return _get_tenant_session


async def _seed_permissions(engine, rows):
    async with AsyncSession(engine) as session:
        return await _seed_table_idempotent(session, "permissions", rows, Permission)


def _build_app(monkeypatch, engine) -> FastAPI:
    """Registered /tenants/permissions router with permissive deps."""

    async def _allow() -> bool:
        return True

    async def _fake_tenant():
        return SimpleNamespace(id=1)

    from tenant2fast_fastapi import dependencies as deps_pkg
    from tenant2fast_fastapi.databases import tenant_db_factory as db_factory

    monkeypatch.setattr(deps_pkg, "has_tenant_permission", lambda *a, **k: _allow)
    monkeypatch.setattr(deps_pkg, "get_current_tenant", _fake_tenant)
    monkeypatch.setattr(db_factory, "get_tenant_session", _session_factory(engine))

    tpr = importlib.import_module("tenant2fast_fastapi.routers.tenant_permissions_router")
    tpr = importlib.reload(tpr)
    app = FastAPI(title="Tenant Permissions Test App")
    app.include_router(tpr.tenant_permissions_router)
    return app


async def _get_permissions(engine, monkeypatch):
    app = _build_app(monkeypatch, engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get("/tenants/permissions/")


@pytest.mark.asyncio
async def test_list_permissions_with_category_returns_200_and_category(monkeypatch):
    """Permission seeded with category_id → 200 and int permission_category_id."""
    engine = await _tenant_engine()
    await _seed_permissions(
        engine, [{"id": 1, "name": "view_tenant_info", "category_id": 1}]
    )

    response = await _get_permissions(engine, monkeypatch)

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["permissions"] == [
        {"id": 1, "name": "view_tenant_info", "permission_category_id": 1}
    ]
    await engine.dispose()


@pytest.mark.asyncio
async def test_list_permissions_without_category_returns_200_and_null(monkeypatch):
    """Permission without category_id → 200 with permission_category_id null."""
    engine = await _tenant_engine()
    await _seed_permissions(
        engine,
        [
            {"id": 1, "name": "view_tenant_info", "category_id": 1},
            {"id": 2, "name": "edit_tenant_info"},
        ],
    )

    response = await _get_permissions(engine, monkeypatch)

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    by_id = {p["id"]: p for p in body["permissions"]}
    assert by_id[1]["permission_category_id"] == 1
    assert by_id[2]["permission_category_id"] is None
    await engine.dispose()


@pytest.mark.asyncio
async def test_get_single_permission_null_safe(monkeypatch):
    """GET /tenants/permissions/{id} with a category-less permission → 200 null."""
    engine = await _tenant_engine()
    await _seed_permissions(engine, [{"id": 2, "name": "edit_tenant_info"}])

    app = _build_app(monkeypatch, engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/tenants/permissions/2")

    assert response.status_code == 200
    body = response.json()
    assert body["permission"] == {
        "id": 2,
        "name": "edit_tenant_info",
        "permission_category_id": None,
    }
    await engine.dispose()