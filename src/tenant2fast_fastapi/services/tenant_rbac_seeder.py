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
    result = await seed("dev", tenant_id=1)

    # Seed ALL tenants (re-seed all existing tenants)
    summary = await seed_all_tenants("dev")
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from ..models.role_model import TenantRole
from ..models.permission_category_model import TenantPermissionCategory
from ..models.permission_model import TenantPermission
from ..databases.tenant_db_factory import get_tenant_session

logger = logging.getLogger(__name__)


# ============================================================================
# Seeder Config
# ============================================================================


def get_seeder_config():
    """
    Return the SeederConfig for this package.

    Used by the seeder orchestrator (pgsqlasync2fast-fastapi) to:
    - Detect table conflicts between packages
    - Determine execution order (priority)
    - Locate the manifest.json for table discovery
    - Identify as a tenant seeder (is_tenant_seeder=True)

    Returns:
        SeederConfig with is_tenant_seeder=True
    """
    from pgsqlasync2fast_fastapi import SeederConfig

    # Path relative to package root: seeders/manifest.json
    # __file__ is tenant2fast_fastapi/services/tenant_rbac_seeder.py, go up 2 levels
    current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    manifest_path = os.path.join(current_dir, "seeders", "manifest.json")

    return SeederConfig(
        connection_name="auth",  # Tenant seeders use auth for tenant enumeration
        manifest_path=manifest_path,
        is_tenant_seeder=True,
        priority=70,
        package_name="tenants2fast-fastapi"
    )


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


async def seed(profile: str, tenant_id: int) -> Dict[str, Any]:
    """
    Seed tenant RBAC data for a specific tenant.

    This function is idempotent - running it multiple times with the same
    data produces the same result (no duplicates).

    Args:
        profile: Profile folder name (e.g., "dev", "prod")
        tenant_id: The tenant ID to seed

    Returns:
        Dictionary with seeding results: {tables_seeded, rows_seeded, errors}
    """
    result = {
        "tenant_id": tenant_id,
        "tables_seeded": 0,
        "rows_seeded": 0,
        "errors": []
    }

    config = get_seeder_config()

    try:
        # Get tenant-specific session
        session = await get_tenant_session(tenant_id)

        async with session:
            # Load manifest
            manifest = _load_manifest(config.manifest_path)

            # Get load order
            table_order = manifest.get("load_order", ["categories", "roles", "permissions"])

            # Track loaded tables for FK validation
            loaded_tables: Dict[str, list[Dict[str, Any]]] = {}

            # First pass: load all data
            for table_name in table_order:
                rows = _load_table_data(table_name, config.manifest_path, profile)
                if not rows:
                    logger.debug(f"No data for table '{table_name}' in profile '{profile}'")
                    continue
                loaded_tables[table_name] = rows

            # Second pass: seed each table
            for table_name in table_order:
                rows = loaded_tables.get(table_name, [])
                if not rows:
                    continue

                model_class = _get_model_class(table_name)
                if model_class is None:
                    logger.warning(f"No model class for table '{table_name}', skipping")
                    continue

                # Seed idempotently
                inserted, skipped = await _seed_table_idempotent(
                    session, table_name, rows, model_class
                )
                result["rows_seeded"] += inserted
                result["tables_seeded"] += 1
                logger.info(f"Seeded table '{table_name}' for tenant {tenant_id}: {inserted} inserted, {skipped} skipped")

        logger.info(f"✅ Seeding completed for tenant {tenant_id}")

    except Exception as e:
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
                        "tenant_id": tenant_id,
                        "status": "failed",
                        "errors": seed_result["errors"]
                    })
                    logger.error(f"❌ Failed to seed tenant {tenant_id}: {seed_result['errors']}")
                else:
                    summary["succeeded"] += 1
                    summary["results"].append({
                        "tenant_id": tenant_id,
                        "status": "succeeded",
                        "rows_seeded": seed_result["rows_seeded"]
                    })
                    logger.info(f"✅ Seeded tenant {tenant_id} successfully")
            except Exception as e:
                summary["failed"] += 1
                summary["results"].append({
                    "tenant_id": tenant_id,
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


def _get_model_class(table_name: str):
    """Map table name to SQLModel class."""
    mapping = {
        "categories": TenantPermissionCategory,
        "roles": TenantRole,
        "permissions": TenantPermission,
    }
    return mapping.get(table_name)


async def _seed_table_idempotent(
    session: AsyncSession,
    table_name: str,
    rows: list[Dict[str, Any]],
    model_class: type
) -> tuple[int, int]:
    """
    Seed a table idempotently by checking if rows exist by ID.

    Args:
        session: SQLModel AsyncSession
        table_name: Name of the table (for logging)
        rows: List of row dictionaries with explicit IDs
        model_class: SQLModel class for the table

    Returns:
        Tuple of (rows_inserted, rows_skipped)
    """
    rows_inserted = 0
    rows_skipped = 0

    for row in rows:
        row_id = row.get("id")
        if row_id is None:
            logger.warning(f"Skipping row without ID in table '{table_name}'")
            rows_skipped += 1
            continue

        # Check if row already exists by ID
        result = await session.exec(
            select(model_class).where(model_class.id == row_id)
        )
        existing = result.one_or_none()

        if existing is not None:
            logger.debug(f"Skipping existing row id={row_id} in table '{table_name}'")
            rows_skipped += 1
            continue

        # Insert new row
        try:
            obj = model_class(**row)
            session.add(obj)
            await session.commit()
            rows_inserted += 1
            logger.debug(f"Inserted row id={row_id} in table '{table_name}'")
        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to insert row in table '{table_name}': {e}")
            raise

    return rows_inserted, rows_skipped


# ============================================================================
# Legacy Function - Backward Compatibility
# ============================================================================


async def seed_tenant_rbac(tenant_id: int):
    """
    Legacy seeding function for backward compatibility.

    Args:
        tenant_id: The tenant ID to seed

    Note:
        Prefer using seed(profile, tenant_id) for new code.
    """
    return await seed("dev", tenant_id)


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "get_seeder_config",
    "seed",
    "seed_all_tenants",
    "seed_tenant_rbac",  # Legacy compatibility
]