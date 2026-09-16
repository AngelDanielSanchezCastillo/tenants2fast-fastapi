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
- CLI: defaults to dry-run; --apply mutates; --tenant N scopes to one tenant

Run with:
  uv run pytest tests/test_owner_cleanup.py -v
"""

from __future__ import annotations

import json

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

ORPHAN_ID = 99
OWNER_ID = 1


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
        session.add(Role(id=OWNER_ID, name="Owner", is_active=True))
        session.add(Role(id=ORPHAN_ID, name="OWNER", is_active=True))
        session.add(Permission(id=1, name="p1"))
        session.add(Permission(id=2, name="p2"))
        session.add(User(id=1, auth_user_id=11))
        # Orphan grants: p1 (shared w/ Owner when owner_has_grant) + p2 (unique).
        # Explicit ids: SQLite does not autoincrement the BigInteger PK.
        session.add(PermissionRole(id=101, role_id=ORPHAN_ID, permission_id=1))
        session.add(PermissionRole(id=102, role_id=ORPHAN_ID, permission_id=2))
        session.add(RoleUser(id=201, role_id=ORPHAN_ID, user_id=1))
        # Merge pairs already owned by Owner.
        if owner_has_grant:
            session.add(PermissionRole(id=103, role_id=OWNER_ID, permission_id=1))
            session.add(RoleUser(id=202, role_id=OWNER_ID, user_id=1))
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
            "roles": sorted((r.id, r.name) for r in roles),
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

    engine = await _tenant_engine()
    await _seed_orphan_state(engine)
    before = await _db_snapshot(engine)
    monkeypatch.setattr(cleanup, "get_tenant_session", _session_factory(engine))

    report = await cleanup.cleanup_owner_role(1, dry_run=True)

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

    engine = await _tenant_engine()
    await _seed_orphan_state(engine)
    monkeypatch.setattr(cleanup, "get_tenant_session", _session_factory(engine))

    report = await cleanup.cleanup_owner_role(1, dry_run=False, snapshot_dir=tmp_path)

    # Grants: both on Owner; the previously-existing (Owner, p1) was NOT
    # duplicated (merged) — exactly one row per pair.
    after = await _db_snapshot(engine)
    assert after["roles"] == [(OWNER_ID, "Owner")]
    assert after["grants"] == [(OWNER_ID, 1), (OWNER_ID, 2)]
    assert after["role_users"] == [(OWNER_ID, 1)]
    assert report["orphan_deleted"] is True
    assert report["owner_created"] is False

    # Snapshot JSON exists under backups layout: <dir>/<ts>/tenant_1.json
    snaps = sorted(tmp_path.glob("*/tenant_1.json"))
    assert len(snaps) == 1
    payload = json.loads(snaps[0].read_text())
    assert payload["tenant_id"] == 1
    assert payload["orphan_role"]["name"] == "OWNER"
    assert {g["role"] for g in payload["grant_rows"]} == {"OWNER"}
    await engine.dispose()


@pytest.mark.asyncio
async def test_cleanup_apply_without_merge_pairs_reassigns_all(monkeypatch, tmp_path):
    """When Owner has no grants yet, every orphan grant is reassigned (not deleted)."""
    from tenant2fast_fastapi.utils import tenant_owner_cleanup as cleanup

    engine = await _tenant_engine()
    await _seed_orphan_state(engine, owner_has_grant=False)
    monkeypatch.setattr(cleanup, "get_tenant_session", _session_factory(engine))

    report = await cleanup.cleanup_owner_role(1, dry_run=False, snapshot_dir=tmp_path)

    after = await _db_snapshot(engine)
    assert after["grants"] == [(OWNER_ID, 1), (OWNER_ID, 2)]
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

    engine = await _tenant_engine()
    await _seed_orphan_state(engine)
    monkeypatch.setattr(cleanup, "get_tenant_session", _session_factory(engine))

    await cleanup.cleanup_owner_role(1, dry_run=False, snapshot_dir=tmp_path)
    clean_before = await _db_snapshot(engine)

    second = await cleanup.cleanup_owner_role(1, dry_run=False, snapshot_dir=tmp_path)

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

    engine = await _tenant_engine()
    async with AsyncSession(engine) as session:
        session.add(Role(id=ORPHAN_ID, name="OWNER", is_active=True))
        session.add(Permission(id=1, name="p1"))
        session.add(User(id=1, auth_user_id=11))
        session.add(PermissionRole(id=101, role_id=ORPHAN_ID, permission_id=1))
        await session.commit()
    monkeypatch.setattr(cleanup, "get_tenant_session", _session_factory(engine))

    report = await cleanup.cleanup_owner_role(1, dry_run=False, snapshot_dir=tmp_path)

    after = await _db_snapshot(engine)
    assert after["roles"] == [(OWNER_ID, "Owner")]
    assert after["grants"] == [(OWNER_ID, 1)]
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

    engine = await _tenant_engine()
    async with AsyncSession(engine) as session:
        session.add(Role(id=ORPHAN_ID, name="OWNER", is_active=True))
        session.add(Permission(id=1, name="p1"))
        session.add(User(id=1, auth_user_id=11))
        session.add(PermissionRole(id=101, role_id=ORPHAN_ID, permission_id=1))
        await session.commit()
    monkeypatch.setattr(cleanup, "get_tenant_session", _session_factory(engine))

    report = await cleanup.cleanup_owner_role(1, dry_run=True)

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

    async def _fake_active_tenants() -> list[int]:
        return [1, 2]

    monkeypatch.setattr(cleanup, "_list_active_tenants", _fake_active_tenants)

    summary = await cleanup.cleanup_all_tenants(dry_run=True)

    assert summary["total"] == 2
    assert summary["processed"] == 2
    assert summary["results"][0]["tenant_id"] == 1
    assert summary["results"][1]["tenant_id"] == 2
    assert all(r["orphan_found"] is True for r in summary["results"])
    await engine.dispose()


def test_cli_defaults_to_dry_run_and_scopes_by_tenant(monkeypatch):
    """CLI without --apply runs dry-run; --tenant N scopes to one tenant."""
    from tenant2fast_fastapi.utils import tenant_owner_cleanup as cleanup

    captured = {}

    async def fake_cleanup(tenant_id, dry_run=False, snapshot_dir=None):
        captured["tenant_id"] = tenant_id
        captured["dry_run"] = dry_run
        return {"tenant_id": tenant_id, "dry_run": dry_run}

    async def fake_all(dry_run=False, snapshot_dir=None):
        captured["all"] = True
        captured["dry_run"] = dry_run
        return {"all": True, "dry_run": dry_run}

    monkeypatch.setattr(cleanup, "cleanup_owner_role", fake_cleanup)
    monkeypatch.setattr(cleanup, "cleanup_all_tenants", fake_all)

    # Default: dry-run on one tenant.
    assert cleanup.main(["--tenant", "7"]) == 0
    assert captured == {"tenant_id": 7, "dry_run": True}

    # --apply on one tenant.
    captured.clear()
    assert cleanup.main(["--tenant", "7", "--apply"]) == 0
    assert captured == {"tenant_id": 7, "dry_run": False}

    # No --tenant: all tenants, still dry-run by default.
    captured.clear()
    assert cleanup.main([]) == 0
    assert captured == {"all": True, "dry_run": True}
