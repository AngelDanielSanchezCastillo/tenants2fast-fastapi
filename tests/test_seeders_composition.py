"""Tenant seeder composition: additive merge, override, disable (ODD-5)."""

from __future__ import annotations

import json
from uuid import uuid7

import pytest
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from tenant2fast_fastapi.models.bases import tenant_metadata
from tenant2fast_fastapi.models.role_model import Role
from tenant2fast_fastapi.seeders import (
    TenantSeederConfig,
    TenantSeederConflictError,
    TenantSeederOrchestrator,
    register_tenant_package_seeders,
    clear_tenant_package_registry,
)


@pytest.fixture
async def engine(monkeypatch):
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(tenant_metadata.create_all)

    async def _session(_tenant_id):
        return AsyncSession(eng, expire_on_commit=False)

    monkeypatch.setattr("tenant2fast_fastapi.seeders.get_tenant_engine", lambda _t: eng)
    monkeypatch.setattr("tenant2fast_fastapi.seeders.get_tenant_session", _session)
    yield eng
    await eng.dispose()


def _app_config(tmp_path, *, overrides=None, merge_tables=None, role_name="CustomRole"):
    root = tmp_path / "app"
    root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "version": "2.0",
        "strict": True,
        "boot": {
            "dev": {
                "tables": {
                    "roles": {
                        "file": "roles.json",
                        "mode": "upsert",
                        "natural_key": ["name"],
                    }
                },
                "dependencies": {"roles": []},
            }
        },
    }
    (root / "manifest.json").write_text(json.dumps(manifest))
    (root / "roles.json").write_text(
        json.dumps([{"id": str(uuid7()), "name": role_name, "description": None}])
    )
    return TenantSeederConfig(
        package_name="app-seeders",
        manifest_path=str(root / "manifest.json"),
        model_registry={"roles": Role},
        priority=90,
        overrides=overrides or [],
        merge_tables=merge_tables or [],
    )


async def _roles(engine):
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        return [r.name for r in (await session.execute(select(Role))).scalars().all()]


@pytest.mark.asyncio
async def test_merge_tables_add_rows_from_both_packages(tmp_path, engine):
    base = TenantSeederConfig()  # tenants2fast RBAC
    app = _app_config(tmp_path, merge_tables=["roles"])
    orchestrator = TenantSeederOrchestrator(profile="dev", configs=[base, app])

    result = await orchestrator.seed_tenant(uuid7())
    assert result.success, result.errors
    names = set(await _roles(engine))
    assert {"Owner", "Admin", "Member", "CustomRole"} <= names


@pytest.mark.asyncio
async def test_override_takes_table_over(tmp_path, engine):
    base = TenantSeederConfig()
    app = _app_config(tmp_path, overrides=["roles"], role_name="OnlyRole")
    orchestrator = TenantSeederOrchestrator(profile="dev", configs=[base, app])

    result = await orchestrator.seed_tenant(uuid7())
    assert result.success, result.errors
    names = set(await _roles(engine))
    assert names == {"OnlyRole"}


def test_conflict_without_merge_or_override(tmp_path):
    clear_tenant_package_registry()
    base = TenantSeederConfig()
    app = _app_config(tmp_path)  # no merge/override
    register_tenant_package_seeders(base)
    with pytest.raises(TenantSeederConflictError, match="roles"):
        register_tenant_package_seeders(app)
    clear_tenant_package_registry()
    register_tenant_package_seeders(TenantSeederConfig())


@pytest.mark.asyncio
async def test_disabled_package_is_skipped(tmp_path, engine):
    base = TenantSeederConfig()
    app = _app_config(tmp_path, merge_tables=["roles"], role_name="DisabledRole")
    app.disabled = True
    orchestrator = TenantSeederOrchestrator(profile="dev", configs=[base, app])

    result = await orchestrator.seed_tenant(uuid7())
    assert result.success
    names = set(await _roles(engine))
    assert "DisabledRole" not in names
    assert {"Owner", "Admin", "Member"} <= names
