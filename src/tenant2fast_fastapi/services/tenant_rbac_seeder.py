"""
Tenant RBAC Seeder - Multi-Package Standard Format.

This module provides the tenant-aware seeder for the tenants2fast-fastapi package.
It seeds roles, categories, and permissions into EACH tenant database.

Key difference from other packages:
- is_tenant_seeder=True: This seeder seeds individual tenant databases
- seed(profile, tenant_id): Seeds ONE specific tenant
- seed_all_tenants(profile): Iterates ALL tenants from auth DB and seeds each

Example usage:
    from tenant2fast_fastapi.seeder import seed, seed_all_tenants, get_seeder_config

    # Seed a specific tenant
    result = await seed("dev", tenant_id=<uuid>)

    # Seed ALL tenants (re-seed all existing tenants)
    summary = await seed_all_tenants("dev")
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from tools2fast_fastapi import active_only as active_only_query

from ..models.role_model import Role
from ..models.permission_category_model import Category
from ..models.permission_model import Permission
from ..databases.tenant_db_factory import get_tenant_session
from ..settings import settings
from permissions2fast_fastapi.services.route_seeder import seed_global_routes
from pgsqlasync2fast_fastapi.seeder import insert_if_missing
from .route_seeder import seed_tenant_routes

logger = logging.getLogger(__name__)


# ============================================================================
# Seeder Config
# ============================================================================


def get_seeder_config():
    """
    Return the tenant seeder configuration.

    Delegates to the new ODD-5 seeder module (manifest v2.0 + model registry).
    """
    from ..seeders import get_seeder_config as _get_seeder_config

    return _get_seeder_config()


# ============================================================================
# Tenant Seeding Logic
# ============================================================================


def _load_manifest(manifest_path: str) -> Dict[str, Any]:
    """Load and parse a manifest.json file."""
    path = Path(manifest_path)
    if not path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_table_data(table_name: str, manifest_path: str, profile: str) -> list[Dict[str, Any]]:
    """Load table data from a JSON file in the profile folder."""
    manifest = _load_manifest(manifest_path)
    table_config = manifest["tables"].get(table_name, {})
    file_name = table_config.get("file", f"{table_name}.json")

    manifest_dir = Path(manifest_path).parent
    json_path = manifest_dir / profile / file_name

    if not json_path.exists():
        logger.warning(f"Seed data not found for table '{table_name}' in profile '{profile}': {json_path}")
        return []

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(f"Table '{table_name}' data must be a list, got {type(data).__name__}")

    return data


async def seed(profile: str, tenant_id: UUID) -> Dict[str, Any]:
    """
    Seed tenant RBAC data for a specific tenant.

    Delegates to the ODD-5 ``TenantSeederOrchestrator`` (manifest v2.0 with
    explicit uuid7 literals and natural-key idempotency).

    Args:
        profile: Profile name (dev/prod).
        tenant_id: The tenant ID (UUID) to seed.

    Returns:
        Dictionary with seeding results: {tables_seeded, rows_seeded, errors}
    """
    from ..seeders import TenantSeederOrchestrator

    result: Dict[str, Any] = {
        "tenant_id": str(tenant_id),
        "tables_seeded": 0,
        "rows_seeded": 0,
        "errors": [],
    }

    try:
        # Pin to this package's own config: app contributions are seeded by the
        # app through the registry, not implicitly from this internal call.
        orchestrator = TenantSeederOrchestrator(
            profile=profile, config=get_seeder_config()
        )
        seeding = await orchestrator.seed_tenant(tenant_id)
        result["tables_seeded"] = seeding.tables_seeded
        result["rows_seeded"] = seeding.rows_inserted + seeding.rows_updated
        result["errors"] = list(seeding.errors)
    except Exception as e:  # noqa: BLE001 - reported in the result
        error_msg = f"Seeding failed for tenant {tenant_id}: {e}"
        logger.error(error_msg)
        result["errors"].append(error_msg)

    return result


async def seed_all_tenants(profile: str) -> Dict[str, Any]:
    """
    Seed RBAC data for ALL tenants in the auth database.

    This iterates through all tenants in the auth DB and seeds each one.
    If one tenant fails, the error is logged but seeding continues to the next.

    Args:
        profile: Profile folder name (e.g., "dev", "prod")

    Returns:
        Dictionary with summary: {total_tenants, succeeded, failed, results}
    """
    from pgsqlasync2fast_fastapi.connection import get_manager
    from sqlmodel.ext.asyncio.session import AsyncSession
    from sqlmodel import select
    from ..models.tenant_model import Tenant

    summary = {
        "profile": profile,
        "total_tenants": 0,
        "succeeded": 0,
        "failed": 0,
        "results": []
    }

    try:
        # Get all tenants from auth DB
        manager = get_manager()
        auth_engine = manager.get_engine("auth")

        async with AsyncSession(auth_engine) as session:
            result = await session.exec(select(Tenant))
            tenants = result.all()
            summary["total_tenants"] = len(tenants)

        # Seed each tenant
        for tenant in tenants:
            tenant_id = tenant.id
            logger.info(f"Seeding tenant {tenant_id} ({tenant.name})...")

            try:
                seed_result = await seed(profile, tenant_id)
                if seed_result["errors"]:
                    summary["failed"] += 1
                    summary["results"].append({
                        "tenant_id": str(tenant_id),
                        "status": "failed",
                        "errors": seed_result["errors"]
                    })
                    logger.error(f"❌ Failed to seed tenant {tenant_id}: {seed_result['errors']}")
                else:
                    summary["succeeded"] += 1
                    summary["results"].append({
                        "tenant_id": str(tenant_id),
                        "status": "succeeded",
                        "rows_seeded": seed_result["rows_seeded"]
                    })
                    logger.info(f"✅ Seeded tenant {tenant_id} successfully")
            except Exception as e:
                summary["failed"] += 1
                summary["results"].append({
                    "tenant_id": str(tenant_id),
                    "status": "error",
                    "error": str(e)
                })
                logger.error(f"❌ Error seeding tenant {tenant_id}: {e}")
                # Continue to next tenant

    except Exception as e:
        logger.error(f"Failed to enumerate tenants: {e}")
        summary["error"] = str(e)

    logger.info(f"🏁 seed_all_tenants completed: {summary['succeeded']}/{summary['total_tenants']} succeeded")
    return summary


# ============================================================================
# RBAC Re-Seed Orchestration (multi-tenant platform service)
# ============================================================================


async def reseed_all_rbac(
    profile: str,
    global_manifest: Any,
    tenant_manifest: Any,
    *,
    active_only: bool = True,
) -> dict[str, Any]:
    """
    Re-seed RBAC for a multi-tenant deployment (GLOBAL + TENANT planes).

    This is the reusable platform orchestration a multi-tenant client calls at
    boot with its own declarative manifests:

    1. GLOBAL routes are seeded on the auth DB via
       ``permissions2fast_fastapi.seed_global_routes`` (auth engine "auth").
    2. Active tenants are enumerated from the auth DB (``active_only`` filters
       ``Tenant.deleted_at IS NULL``).
    3. For each tenant: ``seed(profile, tenant_id)`` (roles, categories,
       permissions + Owner grant) and then
       ``tenant2fast_fastapi.seed_tenant_routes`` on that tenant's DB.
    4. Per-tenant failures are logged and non-fatal (the loop continues).

    Args:
        profile: Active profile (e.g. ``"dev"`` or ``"prod"``).
        global_manifest: List of permissions2fast ``RouteSpec`` (GLOBAL plane).
        tenant_manifest: List of tenants2fast ``RouteSpec`` (TENANT plane).
        active_only: When True (default) only tenants with
            ``deleted_at IS NULL`` are re-seeded; when False every tenant is included.

    Returns:
        Summary dict: ``total``, ``succeeded``, ``failed``, ``errors``,
        ``global_routes``, ``tenant_routes``.
    """
    from pgsqlasync2fast_fastapi.connection import get_manager
    from sqlmodel import select

    from ..models.tenant_model import Tenant

    summary: dict[str, Any] = {
        "total": 0,
        "succeeded": 0,
        "failed": 0,
        "errors": [],
        "global_routes": 0,
        "tenant_routes": 0,
    }

    # Accept JSON manifest paths (preferred) or pre-built RouteSpec lists.
    if isinstance(global_manifest, (str, Path)):
        from permissions2fast_fastapi import load_route_manifest as load_global

        global_manifest = load_global(global_manifest)
    if isinstance(tenant_manifest, (str, Path)):
        from .route_manifest import load_route_manifest as load_tenant

        tenant_manifest = load_tenant(tenant_manifest)


    try:
        # Session de auth (misma vía que seed_all_tenants: manager "auth").
        manager = get_manager()
        auth_engine = manager.get_engine("auth")

        async with AsyncSession(auth_engine) as session:
            # 1. GLOBAL routes -> permissions2fast sobre la BD auth (profile-aware).
            try:
                gresult = await seed_global_routes(
                    session, global_manifest, profile=profile
                )
                await session.commit()
                summary["global_routes"] = gresult["routes"]
            except Exception as exc:
                msg = f"Global manifest seeding failed: {exc}"
                logger.exception(msg)
                summary["errors"].append(msg)

            # 2. Enumerar tenants (filtro activos cuando active_only=True).
            stmt = select(Tenant)
            if active_only:
                stmt = active_only_query(stmt)
            result = await session.exec(stmt)
            tenants = result.all()
            summary["total"] = len(tenants)

            if not tenants:
                logger.info("No tenants found for RBAC re-seed")
                return summary

            logger.info(
                f"RBAC re-seed: {len(tenants)} tenants with profile '{profile}'"
            )

            # 3. Por cada tenant: seed() RBAC + rutas TENANT en su BD.
            for tenant in tenants:
                try:
                    seed_result = await seed(profile, tenant.id)
                    if seed_result.get("errors"):
                        logger.warning(
                            f"Tenant {tenant.id}: seed() reported errors: "
                            f"{seed_result['errors']}"
                        )

                    async with await get_tenant_session(tenant.id) as tsession:
                        tresult = await seed_tenant_routes(
                            tsession, tenant_manifest, profile=profile
                        )
                        await tsession.commit()
                        summary["tenant_routes"] += tresult["tenant_routes"]

                    summary["succeeded"] += 1
                    logger.debug(f"RBAC re-seed OK for tenant {tenant.id}")

                except Exception as exc:
                    # Fallo por tenant: se registra y se continúa con el siguiente.
                    msg = f"Tenant {tenant.id}: {exc}"
                    logger.exception(f"RBAC re-seed FAILED — {msg}")
                    summary["failed"] += 1
                    summary["errors"].append(msg)

    except Exception as exc:
        logger.error(f"Failed to enumerate tenants: {exc}")
        summary["error"] = str(exc)

    if summary["failed"] == 0:
        logger.info(
            f"🏁 RBAC re-seed complete: {summary['succeeded']}/"
            f"{summary['total']} succeeded"
        )
    else:
        logger.warning(
            f"🏁 RBAC re-seed complete: {summary['succeeded']}/"
            f"{summary['total']} succeeded, {summary['failed']} failed"
        )
    return summary


def _get_model_class(table_name: str):
    """Map table name to SQLModel class."""
    mapping = {
        "categories": Category,
        "roles": Role,
        "permissions": Permission,
    }
    return mapping.get(table_name)


# Natural-key lookup field per table — used for idempotent seeding with UUIDs.
# Each seeded row is identified by this field so the same name never produces
# duplicate rows regardless of how many times the seeder runs.
_NATURAL_KEY: dict[str, str] = {
    "categories": "name",
    "roles": "name",
    "permissions": "name",
}

# Seeder JSON keys that differ from the model field names. Mapped on load so
# the seed file stays declarative ("category_name") while the model owns the
# storage name ("permission_category_id").
_FIELD_ALIASES: dict[str, dict[str, str]] = {
    "permissions": {"category_name": "permission_category_id"},
}

# Model fields that are the destination of a _FIELD_ALIASES entry; only these
# are re-synced on reseed (category_name → permission_category_id).
_ALIAS_DEST_FIELDS = frozenset(
    dst for aliases in _FIELD_ALIASES.values() for dst in aliases.values()
)

# FK resolution: alias source field → (referenced table, referenced natural key).
# When the seeder sees a string value for these fields (e.g. "System"), it
# resolves the UUID from the referenced table by natural key.
_FK_RESOLUTION: dict[str, dict[str, tuple[str, str]]] = {
    "permissions": {"category_name": ("categories", "name")},
}


def _map_row_fields(table_name: str, row: dict[str, Any]) -> dict[str, Any]:
    """Normalize seeder JSON keys onto model fields for ``table_name``."""
    mapped = dict(row)
    for src, dst in _FIELD_ALIASES.get(table_name, {}).items():
        if src in mapped:
            mapped[dst] = mapped.pop(src)
    # Drop "id" if present — UUIDs are auto-generated, lookup is by natural key.
    mapped.pop("id", None)
    return mapped


async def _resolve_fk_references(
    session: AsyncSession,
    table_name: str,
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Resolve string FK references (natural keys) to UUIDs for ``table_name``.

    For each row, if a field is declared in ``_FK_RESOLUTION`` for this table
    and its value is a string (not a UUID), look up the referenced row by
    natural key and replace the value with its UUID.
    """
    resolution = _FK_RESOLUTION.get(table_name)
    if not resolution:
        return rows

    resolved_rows = []
    for row in rows:
        new_row = dict(row)
        for src_field, (ref_table, ref_key) in resolution.items():
            value = new_row.get(src_field)
            if value is None or not isinstance(value, str):
                continue
            # Try to parse as UUID — if it already is one, skip resolution.
            try:
                UUID(value)
                continue
            except ValueError:
                pass
            # Resolve by natural key from the referenced table.
            ref_model = _get_model_class(ref_table)
            if ref_model is None:
                logger.warning(
                    f"Cannot resolve FK '{src_field}={value!r}' — "
                    f"no model for table '{ref_table}'"
                )
                continue
            result = await session.exec(
                select(ref_model).where(getattr(ref_model, ref_key) == value)
            )
            ref_row = result.one_or_none()
            if ref_row is None:
                logger.warning(
                    f"Cannot resolve FK '{src_field}={value!r}' — "
                    f"no {ref_table} with {ref_key}={value!r}"
                )
                continue
            new_row[src_field] = ref_row.id
        resolved_rows.append(new_row)
    return resolved_rows


def _sync_alias_fields(model_class: type, existing, mapped: dict[str, Any]) -> bool:
    """Update alias-mapped fields that differ on an existing row.

    Returns True when a change is pending on the session. Only fields that are
    the destination of a ``_FIELD_ALIASES`` entry are synced (e.g.
    ``permission_category_id``); other fields keep their stored values.
    """
    changed = False
    for key, value in mapped.items():
        if key in ("id",) or key not in _ALIAS_DEST_FIELDS:
            continue
        if getattr(existing, key, None) != value:
            setattr(existing, key, value)
            changed = True
    if changed:
        return True
    return False


async def _seed_table_idempotent(
    session: AsyncSession,
    table_name: str,
    rows: list[Dict[str, Any]],
    model_class: type
) -> tuple[int, int]:
    """
    Seed a table idempotently (skip existing rows by natural key, sync alias FKs).

    Lookup uses the natural key (``name`` for categories/roles/permissions)
    instead of ``id`` — UUIDs are auto-generated via UUIDIdMixin, so a fixed
    integer ID from the seeder JSON is meaningless.

    Args:
        session: SQLModel AsyncSession
        table_name: Name of the table (for logging)
        rows: List of row dictionaries
        model_class: SQLModel class for the table

    Returns:
        Tuple of (rows_inserted, rows_skipped)
    """
    rows_inserted = 0
    rows_skipped = 0
    natural_key = _NATURAL_KEY.get(table_name, "name")

    for row in rows:
        # Normalize seeder JSON keys onto model fields (category_id → permission_category_id).
        mapped = _map_row_fields(table_name, row)

        lookup_value = mapped.get(natural_key)
        if lookup_value is None:
            logger.warning(f"Skipping row without '{natural_key}' in table '{table_name}'")
            rows_skipped += 1
            continue

        # Check if row already exists by natural key.
        result = await session.exec(
            select(model_class).where(getattr(model_class, natural_key) == lookup_value)
        )
        existing = result.one_or_none()

        if existing is not None:
            if _sync_alias_fields(model_class, existing, mapped):
                session.add(existing)
                await session.commit()
                logger.debug(f"Updated row {natural_key}={lookup_value!r} in table '{table_name}'")
            else:
                logger.debug(f"Skipping existing row {natural_key}={lookup_value!r} in table '{table_name}'")
            rows_skipped += 1
            continue

        # Shared primitive handles the INSERT (flush only; commit below).
        try:
            await insert_if_missing(
                session,
                model_class,
                lookup={natural_key: lookup_value},
                defaults={k: v for k, v in mapped.items() if k != natural_key},
            )
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to insert row in table '{table_name}': {e}")
            raise
        rows_inserted += 1
        logger.debug(f"Inserted row {natural_key}={lookup_value!r} in table '{table_name}'")

    return rows_inserted, rows_skipped


# ============================================================================
# Legacy Function - Backward Compatibility
# ============================================================================


async def seed_tenant_rbac(tenant_id: UUID, profile: str | None = None):
    """
    Legacy seeding function for backward compatibility.

    Args:
        tenant_id: The tenant ID (UUID) to seed
        profile: Profile folder name (e.g., "dev", "prod").
            When None, uses settings.seed_profile.

    Note:
        Prefer using seed(profile, tenant_id) for new code.
    """
    resolved_profile = profile or settings.seed_profile
    return await seed(resolved_profile, tenant_id)


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "get_seeder_config",
    "seed",
    "seed_all_tenants",
    "seed_tenant_rbac",  # Legacy compatibility
    "reseed_all_rbac",
]
