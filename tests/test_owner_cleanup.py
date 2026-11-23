"""
test_owner_cleanup.py — TDD tests for the 0.7.4 owner-role cleanup migration.

The regression left an orphan "OWNER" role (uppercase) next to the seeded
"Owner": cover-all grants and role/user assignments were attached to the
orphan while ``require_tenant_owner``/route seeding now use "Owner". This
migration must run BEFORE the first boot with the fixed release:

- dry-run reports impact without mutating data
- apply moves PermissionRole + RoleUser grants to "Owner" (merging pairs that
  already exist), deletes the orphan role and writes a JSON snapshot
- idempotent: a second run affects 0 rows
- defensive: creates "Owner" when the tenant has none
- CLI: defaults to dry-run; --apply mutates; --tenant <uuid> scopes to one tenant

Run with:
  uv run pytest tests/test_owner_cleanup.py -v
"""

from __future__ import annotations

import json
from uuid import uuid7

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from tenant2fast_fastapi.models.assignments_model import PermissionRole, RoleUser
from tenant2fast_fastapi.models.bases import tenant_metadata
from tenant2fast_fastapi.models.permission_model import Permission
from tenant2fast_fastapi.models.role_model import Role
from tenant2fast_fastapi.models.user_model import User
from tenant2fast_fastapi.utils.models_loader import import_tenant_models


async def _tenant_engine():
    """Tenant SQLite engine with the tenant RBAC schema only."""
    import_tenant_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(tenant_metadata.create_all)
    return engine


async def _seed_orphan_state(engine, *, owner_has_grant: bool = True):
    """Seed Owner + orphan OWNER + permissions + grants (with/without merge pairs)."""
    async with AsyncSession(engine) as session:
        owner = Role(name="Owner")
        orphan = Role(name="OWNER")
        p1 = Permission(name="p1")
        p2 = Permission(name="p2")
        user = User(auth_user_id=uuid7())
        session.add_all([owner, orphan, p1, p2, user])
        await session.flush()

        # Orphan grants: p1 (shared w/ Owner when owner_has_grant) + p2 (unique).
        session.add(PermissionRole(role_id=orphan.id, permission_id=p1.id))
        session.add(PermissionRole(role_id=orphan.id, permission_id=p2.id))
        session.add(RoleUser(role_id=orphan.id, user_id=user.id))
        # Merge pairs already owned by Owner.
        if owner_has_grant:
            session.add(PermissionRole(role_id=owner.id, permission_id=p1.id))
            session.add(RoleUser(role_id=owner.id, user_id=user.id))
        await session.commit()


def _session_factory(engine):
    """Return a get_tenant_session stand-in bound to ONE SQLite engine."""

    async def _get_tenant_session(tenant_id):
        return AsyncSession(engine, expire_on_commit=False)

    return _get_tenant_session


async def _db_snapshot(engine) -> dict:
    """Read the whole affected state so tests can compare before/after."""
    async with AsyncSession(engine) as session:
        roles = (await session.exec(select(Role))).all()
        grants = (await session.exec(select(PermissionRole))).all()
        role_users = (await session.exec(select(RoleUser))).all()
        return {
            "roles": sorted(((r.id, r.name) for r in roles), key=lambda x: x[1]),
            "grants": sorted((g.role_id, g.permission_id) for g in grants),
            "role_users": sorted((ru.role_id, ru.user_id) for ru in role_users),
        }


# ---------------------------------------------------------------------------
# Dry-run: report only, never mutate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cleanup_dry_run_reports_without_mutating(monkeypatch):
    """dry_run=True reports impact and leaves roles/grants untouched."""
    from tenant2fast_fastapi.utils import tenant_owner_cleanup as cleanup

    tenant_id = uuid7()
    engine = await _tenant_engine()
    await _seed_orphan_state(engine)
    before = await _db_snapshot(engine)
    monkeypatch.setattr(cleanup, "get_tenant_session", _session_factory(engine))

    report = await cleanup.cleanup_owner_role(tenant_id, dry_run=True)

    assert report["dry_run"] is True
    assert report["orphan_found"] is True
    # Dry-run fields describe the projected impact of apply.
    assert report["grants_reassigned"] == 1  # p2 (p1 is a merge pair)
    assert report["grants_deleted"] == 1  # p1 merged into existing row
    assert report["role_users_reassigned"] == 0
    assert report["role_users_deleted"] == 1
    assert report["orphan_deleted"] is True  # apply WOULD delete it
    # Nothing mutated.
    assert await _db_snapshot(engine) == before
    await engine.dispose()


# ---------------------------------------------------------------------------
# Apply: move grants, merge pairs, delete orphan, snapshot
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cleanup_apply_moves_grants_deletes_orphan_and_snapshots(
    monkeypatch, tmp_path
):
    """apply=True reassigns grants, merges duplicate pairs, deletes OWNER, snapshots."""
    from tenant2fast_fastapi.utils import tenant_owner_cleanup as cleanup

    tenant_id = uuid7()
    engine = await _tenant_engine()
    await _seed_orphan_state(engine)
    monkeypatch.setattr(cleanup, "get_tenant_session", _session_factory(engine))

    report = await cleanup.cleanup_owner_role(
        tenant_id, dry_run=False, snapshot_dir=tmp_path
    )

    # Grants: both on Owner; the previously-existing (Owner, p1) was NOT
    # duplicated (merged) — exactly one row per pair.
    after = await _db_snapshot(engine)
    owner = (await _get_role(engine, "Owner"))
    assert [r[1] for r in after["roles"]] == ["Owner"]
    p1 = (await _get_permission(engine, "p1"))
    p2 = (await _get_permission(engine, "p2"))
    assert after["grants"] == sorted([(owner.id, p1.id), (owner.id, p2.id)])
    assert report["orphan_deleted"] is True
    assert report["owner_created"] is False

    # Snapshot JSON exists under backups layout: <dir>/<ts>/tenant_<uuid>.json
    snaps = sorted(tmp_path.glob(f"*/tenant_{tenant_id}.json"))
    assert len(snaps) == 1
    payload = json.loads(snaps[0].read_text())
    assert payload["tenant_id"] == str(tenant_id)
    assert payload["orphan_role"]["name"] == "OWNER"
    assert {g["role"] for g in payload["grant_rows"]} == {"OWNER"}
    await engine.dispose()


async def _get_role(engine, name: str) -> Role:
    async with AsyncSession(engine) as session:
        return (await session.exec(select(Role).where(Role.name == name))).one()


async def _get_permission(engine, name: str) -> Permission:
    async with AsyncSession(engine) as session:
        return (
            await session.exec(select(Permission).where(Permission.name == name))
        ).one()


@pytest.mark.asyncio
async def test_cleanup_apply_without_merge_pairs_reassigns_all(monkeypatch, tmp_path):
    """When Owner has no grants yet, every orphan grant is reassigned (not deleted)."""
    from tenant2fast_fastapi.utils import tenant_owner_cleanup as cleanup

    tenant_id = uuid7()
    engine = await _tenant_engine()
    await _seed_orphan_state(engine, owner_has_grant=False)
    monkeypatch.setattr(cleanup, "get_tenant_session", _session_factory(engine))

    report = await cleanup.cleanup_owner_role(
        tenant_id, dry_run=False, snapshot_dir=tmp_path
    )

    after = await _db_snapshot(engine)
    owner = await _get_role(engine, "Owner")
    p1 = await _get_permission(engine, "p1")
    p2 = await _get_permission(engine, "p2")
    assert after["grants"] == sorted([(owner.id, p1.id), (owner.id, p2.id)])
    assert report["grants_reassigned"] == 2
    assert report["grants_deleted"] == 0
    assert report["role_users_reassigned"] == 1
    await engine.dispose()


# ---------------------------------------------------------------------------
# Idempotency + defensive Owner creation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cleanup_second_run_affects_zero_rows(monkeypatch, tmp_path):
    """A second apply run (tenant already clean) affects no rows."""
    from tenant2fast_fastapi.utils import tenant_owner_cleanup as cleanup

    tenant_id = uuid7()
    engine = await _tenant_engine()
    await _seed_orphan_state(engine)
    monkeypatch.setattr(cleanup, "get_tenant_session", _session_factory(engine))

    await cleanup.cleanup_owner_role(tenant_id, dry_run=False, snapshot_dir=tmp_path)
    clean_before = await _db_snapshot(engine)

    second = await cleanup.cleanup_owner_role(
        tenant_id, dry_run=False, snapshot_dir=tmp_path
    )

    assert second["orphan_found"] is False
    assert second["grants_reassigned"] == 0
    assert second["grants_deleted"] == 0
    assert second["role_users_reassigned"] == 0
    assert second["role_users_deleted"] == 0
    assert await _db_snapshot(engine) == clean_before
    await engine.dispose()


@pytest.mark.asyncio
async def test_cleanup_creates_owner_defensively_when_missing(monkeypatch, tmp_path):
    """Tenant with only the orphan OWNER → Owner is created and gets the grants."""
    from tenant2fast_fastapi.utils import tenant_owner_cleanup as cleanup

    tenant_id = uuid7()
    engine = await _tenant_engine()
    async with AsyncSession(engine) as session:
        orphan = Role(name="OWNER")
        p1 = Permission(name="p1")
        user = User(auth_user_id=uuid7())
        session.add_all([orphan, p1, user])
        await session.flush()
        session.add(PermissionRole(role_id=orphan.id, permission_id=p1.id))
        await session.commit()
    monkeypatch.setattr(cleanup, "get_tenant_session", _session_factory(engine))

    report = await cleanup.cleanup_owner_role(
        tenant_id, dry_run=False, snapshot_dir=tmp_path
    )

    after = await _db_snapshot(engine)
    owner = await _get_role(engine, "Owner")
    p1 = await _get_permission(engine, "p1")
    assert [r[1] for r in after["roles"]] == ["Owner"]
    assert after["grants"] == [(owner.id, p1.id)]
    assert report["owner_created"] is True
    assert report["orphan_deleted"] is True
    await engine.dispose()


# ---------------------------------------------------------------------------
# All tenants + CLI
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cleanup_dry_run_without_owner_reports_projections_without_crashing(
    monkeypatch,
):
    """Dry-run on a tenant with ONLY the orphan: project Owner creation + grant move."""
    from tenant2fast_fastapi.utils import tenant_owner_cleanup as cleanup

    tenant_id = uuid7()
    engine = await _tenant_engine()
    async with AsyncSession(engine) as session:
        orphan = Role(name="OWNER")
        p1 = Permission(name="p1")
        user = User(auth_user_id=uuid7())
        session.add_all([orphan, p1, user])
        await session.flush()
        session.add(PermissionRole(role_id=orphan.id, permission_id=p1.id))
        await session.commit()
    monkeypatch.setattr(cleanup, "get_tenant_session", _session_factory(engine))

    report = await cleanup.cleanup_owner_role(tenant_id, dry_run=True)

    assert report["dry_run"] is True
    assert report["owner_created"] is True
    assert report["grants_reassigned"] == 1
    assert report["orphan_deleted"] is True
    await engine.dispose()


@pytest.mark.asyncio
async def test_cleanup_all_tenants_iterates_every_tenant(monkeypatch):
    """cleanup_all_tenants processes every active tenant id sequentially."""
    from tenant2fast_fastapi.utils import tenant_owner_cleanup as cleanup

    engine = await _tenant_engine()
    await _seed_orphan_state(engine)
    monkeypatch.setattr(cleanup, "get_tenant_session", _session_factory(engine))

    tenant_ids = [uuid7(), uuid7()]

    async def _fake_active_tenants():
        return tenant_ids

    monkeypatch.setattr(cleanup, "_list_active_tenants", _fake_active_tenants)

    summary = await cleanup.cleanup_all_tenants(dry_run=True)

    assert summary["total"] == 2
    assert summary["processed"] == 2
    assert [r["tenant_id"] for r in summary["results"]] == [str(t) for t in tenant_ids]
    assert all(r["orphan_found"] is True for r in summary["results"])
    await engine.dispose()


def test_cli_defaults_to_dry_run_and_scopes_by_tenant(monkeypatch):
    """CLI without --apply runs dry-run; --tenant <uuid> scopes to one tenant."""
    from tenant2fast_fastapi.utils import tenant_owner_cleanup as cleanup

    captured = {}
    tenant_uuid = str(uuid7())

    async def fake_cleanup(tenant_id, dry_run=False, snapshot_dir=None):
        captured["tenant_id"] = str(tenant_id)
        captured["dry_run"] = dry_run
        return {"tenant_id": str(tenant_id), "dry_run": dry_run}

    async def fake_all(dry_run=False, snapshot_dir=None):
        captured["all"] = True
        captured["dry_run"] = dry_run
        return {"all": True, "dry_run": dry_run}

    monkeypatch.setattr(cleanup, "cleanup_owner_role", fake_cleanup)
    monkeypatch.setattr(cleanup, "cleanup_all_tenants", fake_all)

    # Default: dry-run on one tenant.
    assert cleanup.main(["--tenant", tenant_uuid]) == 0
    assert captured == {"tenant_id": tenant_uuid, "dry_run": True}

    # --apply on one tenant.
    captured.clear()
    assert cleanup.main(["--tenant", tenant_uuid, "--apply"]) == 0
    assert captured == {"tenant_id": tenant_uuid, "dry_run": False}

    # No --tenant: all tenants, still dry-run by default.
    captured.clear()
    assert cleanup.main([]) == 0
    assert captured == {"all": True, "dry_run": True}
