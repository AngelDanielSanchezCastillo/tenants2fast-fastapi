"""
Tenant owner-role cleanup migration (tenants2fast-fastapi 0.7.4).

Context
-------
Versions before 0.7.4 seeded a legacy uppercase ``"OWNER"`` role as the
cover-all default (``route_seeder.DEFAULT_TENANT_ROLE``), while the RBAC
seeders ship the canonical ``"Owner"`` role (id=1) and clients assign that
canonical role to the tenant owner. The result was an orphan ``"OWNER"``
role holding cover-all PermissionRole grants and RoleUser assignments that
the owner never received, so ``require_tenant_owner`` (which matches
``"Owner"``) 403'd the real owner.

This module is the pre-boot migration that re-aligns existing tenant data:

- re-assign every orphan ``"OWNER"`` PermissionRole/RoleUser row to ``"Owner"``
- merge pairs that already exist on ``"Owner"`` (delete the orphan row instead
  of duplicating)
- delete the orphan ``"OWNER"`` role
- create ``"Owner"`` defensively when a tenant has none
- write a JSON snapshot of the touched rows BEFORE mutating (apply mode only)
- dry-run mode only reports the projected impact without mutating data
- idempotent: a tenant without ``"OWNER"`` is reported as clean (0 rows)

Operational order (see package rollout): run ``--dry-run`` on every tenant
BEFORE the first boot with 0.7.4, inspect the report, then run ``--apply``
(per tenant or for all tenants). Boot's ``reseed_all_rbac`` is idempotent
afterwards.

CLI::

    # Report impact only (no mutations) for every active tenant
    python -m tenant2fast_fastapi.utils.tenant_owner_cleanup --dry-run

    # Apply for ONE tenant (snapshot written under backups/)
    python -m tenant2fast_fastapi.utils.tenant_owner_cleanup --apply --tenant 1

    # Apply for all active tenants
    python -m tenant2fast_fastapi.utils.tenant_owner_cleanup --apply
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..databases.tenant_db_factory import get_tenant_session
from ..models.assignments_model import PermissionRole, RoleUser
from ..models.role_model import Role

# Canonical cover-all role name (RBAC seeders, id=1) and the legacy orphan.
OWNER_ROLE_NAME = "Owner"
ORPHAN_ROLE_NAME = "OWNER"

# Snapshots default to ./backups/tenant_owner_cleanup/<timestamp>/tenant_<id>.json
DEFAULT_SNAPSHOT_ROOT = Path("backups") / "tenant_owner_cleanup"


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------


def _write_snapshot(
    root: Path,
    tenant_id: int,
    owner: Role | None,
    orphan: Role,
    orphan_grants: list[PermissionRole],
    orphan_role_users: list[RoleUser],
) -> str:
    """Persist the pre-mutation state of every row this migration touches."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    snap_dir = root / ts
    snap_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "migration": "tenant_owner_cleanup",
        "package_version": "0.7.4",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tenant_id": tenant_id,
        "owner_role": {"id": owner.id, "name": owner.name} if owner else None,
        "orphan_role": {"id": orphan.id, "name": orphan.name},
        "grant_rows": [
            {"role": ORPHAN_ROLE_NAME, "permission_id": g.permission_id}
            for g in orphan_grants
        ],
        "role_user_rows": [
            {"role": ORPHAN_ROLE_NAME, "user_id": ru.user_id}
            for ru in orphan_role_users
        ],
    }

    path = snap_dir / f"tenant_{tenant_id}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)


# ---------------------------------------------------------------------------
# Per-tenant cleanup
# ---------------------------------------------------------------------------


async def cleanup_owner_role(
    tenant_id: int,
    *,
    dry_run: bool = False,
    snapshot_dir: str | Path | None = None,
) -> dict[str, Any]:
    """
    Re-align ONE tenant's orphan ``"OWNER"`` role onto the canonical ``"Owner"``.

    Args:
        tenant_id: Auth id of the tenant DB to clean.
        dry_run: When True, only report the projected impact; no writes.
        snapshot_dir: Snapshot root directory; defaults to
            ``./backups/tenant_owner_cleanup``.

    Returns:
        Report dict with per-tenant counters. In dry-run the counters describe
        what ``--apply`` WOULD do; in apply mode they describe what was done.
    """
    report: dict[str, Any] = {
        "tenant_id": tenant_id,
        "dry_run": dry_run,
        "owner_found": False,
        "orphan_found": False,
        "grants_reassigned": 0,
        "grants_deleted": 0,
        "role_users_reassigned": 0,
        "role_users_deleted": 0,
        "owner_created": False,
        "orphan_deleted": False,
    }
    root = Path(snapshot_dir) if snapshot_dir else DEFAULT_SNAPSHOT_ROOT

    async with await get_tenant_session(tenant_id) as session:
        owner = (
            await session.exec(select(Role).where(Role.name == OWNER_ROLE_NAME))
        ).one_or_none()
        orphan = (
            await session.exec(select(Role).where(Role.name == ORPHAN_ROLE_NAME))
        ).one_or_none()
        report["owner_found"] = owner is not None
        report["orphan_found"] = orphan is not None

        # Defensive: guarantee the canonical Owner role exists. "Owner" is a
        # reserved system role (every RBAC seeder declares it as id=1), so it
        # is re-created with that fixed id. A collision means the tenant data
        # was manipulated by hand and must be inspected (fails the tenant).
        if owner is None:
            if dry_run:
                report["owner_created"] = True
            else:
                owner = Role(id=1, name=OWNER_ROLE_NAME, is_active=True)
                session.add(owner)
                await session.commit()
                await session.refresh(owner)
                report["owner_created"] = True

        # Nothing to migrate: report the clean state.
        if orphan is None:
            return report

        orphan_grants = (
            await session.exec(
                select(PermissionRole).where(PermissionRole.role_id == orphan.id)
            )
        ).all()
        orphan_role_users = (
            await session.exec(select(RoleUser).where(RoleUser.role_id == orphan.id))
        ).all()

        if not dry_run:
            report["snapshot"] = _write_snapshot(
                root,
                tenant_id,
                owner,
                orphan,
                list(orphan_grants),
                list(orphan_role_users),
            )

        if owner is None:
            # Dry-run where Owner is missing: nothing on "Owner" to merge yet.
            owner_grant_perms: set[int] = set()
            owner_user_ids: set[int] = set()
        else:
            owner_grant_perms = {
                g.permission_id
                for g in (
                    await session.exec(
                        select(PermissionRole).where(PermissionRole.role_id == owner.id)
                    )
                ).all()
            }
            owner_user_ids = {
                ru.user_id
                for ru in (
                    await session.exec(
                        select(RoleUser).where(RoleUser.role_id == owner.id)
                    )
                ).all()
            }

        if dry_run:
            for grant in orphan_grants:
                if grant.permission_id in owner_grant_perms:
                    report["grants_deleted"] += 1
                else:
                    report["grants_reassigned"] += 1
            for role_user in orphan_role_users:
                if role_user.user_id in owner_user_ids:
                    report["role_users_deleted"] += 1
                else:
                    report["role_users_reassigned"] += 1
            report["orphan_deleted"] = True
            return report

        # Apply: merge pairs that already exist, reassign the rest, delete the orphan.
        for grant in orphan_grants:
            if grant.permission_id in owner_grant_perms:
                await session.delete(grant)
                report["grants_deleted"] += 1
            else:
                grant.role_id = owner.id
                session.add(grant)
                report["grants_reassigned"] += 1

        for role_user in orphan_role_users:
            if role_user.user_id in owner_user_ids:
                await session.delete(role_user)
                report["role_users_deleted"] += 1
            else:
                role_user.role_id = owner.id
                session.add(role_user)
                report["role_users_reassigned"] += 1

        await session.delete(orphan)
        report["orphan_deleted"] = True
        await session.commit()

    return report


# ---------------------------------------------------------------------------
# All-tenants orchestration + CLI
# ---------------------------------------------------------------------------


async def _list_active_tenants() -> list[int]:
    """Enumerate active tenant ids from the auth DB (same pattern as migrations)."""
    from pgsqlasync2fast_fastapi.connection import get_manager

    from ..models.tenant_model import Tenant

    auth_engine = get_manager().get_engine("auth")
    async with AsyncSession(auth_engine) as session:
        result = await session.exec(select(Tenant).where(Tenant.is_active.is_(True)))
        return [t.id for t in result.all()]


async def cleanup_all_tenants(
    *,
    dry_run: bool = False,
    snapshot_dir: str | Path | None = None,
) -> dict[str, Any]:
    """
    Run ``cleanup_owner_role`` on every active tenant.

    Per-tenant failures are recorded and do not stop the loop.
    """
    tenant_ids = await _list_active_tenants()
    summary: dict[str, Any] = {
        "total": len(tenant_ids),
        "processed": 0,
        "results": [],
    }
    for tenant_id in tenant_ids:
        try:
            report = await cleanup_owner_role(
                tenant_id, dry_run=dry_run, snapshot_dir=snapshot_dir
            )
            summary["processed"] += 1
            summary["results"].append(report)
        except (OSError, RuntimeError, ValueError) as exc:
            # Non-fatal: keep cleaning the remaining tenants.
            summary["results"].append({"tenant_id": tenant_id, "error": str(exc)})
    return summary


def build_parser() -> argparse.ArgumentParser:
    """CLI parser: dry-run by default, --apply mutates, --tenant scopes."""
    parser = argparse.ArgumentParser(
        prog="python -m tenant2fast_fastapi.utils.tenant_owner_cleanup",
        description=(
            "Re-align the orphan 'OWNER' role onto the canonical 'Owner' before "
            "the first boot with tenants2fast-fastapi 0.7.4. Defaults to dry-run "
            "(reports impact, writes nothing); --apply mutates and snapshots."
        ),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the migration (default is dry-run).",
    )
    parser.add_argument(
        "--tenant",
        type=int,
        default=None,
        help="Only process this tenant id instead of every active tenant.",
    )
    parser.add_argument(
        "--snapshot-dir",
        default=None,
        help="Snapshot root directory (default: ./backups/tenant_owner_cleanup).",
    )
    return parser


async def _run(argv: list[str] | None) -> int:
    args = build_parser().parse_args(argv)
    dry_run = not args.apply
    if args.tenant is not None:
        result = await cleanup_owner_role(
            args.tenant, dry_run=dry_run, snapshot_dir=args.snapshot_dir
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        summary = await cleanup_all_tenants(
            dry_run=dry_run, snapshot_dir=args.snapshot_dir
        )
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint (also used by ``python -m``)."""
    return asyncio.run(_run(argv))


if __name__ == "__main__":
    raise SystemExit(main())
