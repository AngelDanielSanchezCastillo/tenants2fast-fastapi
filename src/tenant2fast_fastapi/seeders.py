"""
Tenant seeder orchestration (ODD-5).

Wraps pgsqlasync2fast's ``SeederEngine`` to seed tenant databases:
- ``TenantSeederOrchestrator.seed_tenant()``: one tenant
- ``.seed_all_tenants()``: every active tenant (with ``TenantFilter``)
- ``.seed_new_tenant()``: a tenant created at runtime

Composition (same model as the auth lane):
- packages register a ``TenantSeederConfig`` (base seeders)
- ``merge_tables`` lets another package ADD rows to a table (row-level merge;
  natural_key upserts keep it idempotent)
- ``overrides`` gives a package exclusive ownership of a table
- ``disabled`` skips a package entirely; the caller may also include/exclude
  packages for a single run
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Callable
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from tools2fast_fastapi import active_only as active_only_query

from pgsqlasync2fast_fastapi import (
    SeederEngine,
    SeederFilters,
    SeedingResult,
    adopt_explicit_ids,
)

from .databases.tenant_db_factory import get_tenant_engine, get_tenant_session
from .models.permission_category_model import Category
from .models.permission_model import Permission
from .models.role_model import Role
from .models.tenant_model import Tenant

logger = logging.getLogger(__name__)

_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
TENANT_RBAC_MANIFEST_PATH = os.path.join(_PACKAGE_DIR, "seeders", "manifest.json")

TENANT_RBAC_MODEL_REGISTRY: dict[str, type] = {
    "categories": Category,
    "roles": Role,
    "permissions": Permission,
}


@dataclass
class TenantSeederConfig:
    """Configuration for one tenant seeder package/contribution."""

    package_name: str = "tenants2fast-fastapi"
    manifest_path: str = TENANT_RBAC_MANIFEST_PATH
    model_registry: dict[str, type] = field(
        default_factory=lambda: dict(TENANT_RBAC_MODEL_REGISTRY)
    )
    connection: str = "auth"
    priority: int = 70
    #: Tables this package exclusively takes over from another package.
    overrides: list[str] = field(default_factory=list)
    #: Tables this package contributes rows to additively (row-level merge).
    merge_tables: list[str] = field(default_factory=list)
    #: When True the package is skipped by the orchestrator.
    disabled: bool = False


_TENANT_PACKAGE_REGISTRY: dict[str, TenantSeederConfig] = {}


class TenantSeederConflictError(ValueError):
    """Raised when two tenant package seeders overlap without merge/override."""


def _manifest_tables(manifest_path: str) -> set[str]:
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    tables: set[str] = set()
    for layer_name in ("boot", "on_demand"):
        for profile_cfg in manifest.get(layer_name, {}).values():
            tables |= set(profile_cfg.get("tables", {}).keys())
    return tables


def register_tenant_package_seeders(config: TenantSeederConfig) -> None:
    """
    Register a tenant seeder contribution.

    Overlaps are allowed only when either package declares the table in
    ``merge_tables`` (additive rows) or the new one declares it in
    ``overrides`` (exclusive takeover). Otherwise a conflict is raised.
    Re-registering the same ``package_name`` replaces the entry.
    """
    for name, existing in _TENANT_PACKAGE_REGISTRY.items():
        if name == config.package_name:
            continue
        overlap = _manifest_tables(existing.manifest_path) & _manifest_tables(
            config.manifest_path
        )
        if not overlap:
            continue
        resolvable = (
            set(existing.merge_tables)
            | set(config.merge_tables)
            | set(config.overrides)
        )
        unresolved = overlap - resolvable
        if unresolved:
            raise TenantSeederConflictError(
                f"Tables {sorted(unresolved)} conflict between "
                f"'{existing.package_name}' and '{config.package_name}' "
                f"(declare merge_tables or overrides)"
            )

    _TENANT_PACKAGE_REGISTRY[config.package_name] = config


def get_registered_tenant_packages() -> list[TenantSeederConfig]:
    return sorted(_TENANT_PACKAGE_REGISTRY.values(), key=lambda c: c.priority)


def clear_tenant_package_registry() -> None:
    _TENANT_PACKAGE_REGISTRY.clear()


def set_tenant_package_enabled(package_name: str, enabled: bool) -> None:
    config = _TENANT_PACKAGE_REGISTRY.get(package_name)
    if config is None:
        raise KeyError(f"Tenant seeder package not registered: {package_name}")
    config.disabled = not enabled


def disable_tenant_package_seeders(package_name: str) -> None:
    set_tenant_package_enabled(package_name, False)


def enable_tenant_package_seeders(package_name: str) -> None:
    set_tenant_package_enabled(package_name, True)


def get_seeder_config() -> TenantSeederConfig:
    """Return this package's default tenant seeder config."""
    return TenantSeederConfig()


def _resolve_tenant_tables(
    configs: list[TenantSeederConfig],
) -> dict[str, set[str]]:
    """Resolve which tables each package seeds (additive merge vs override)."""
    owners: dict[str, TenantSeederConfig] = {}
    contributions: dict[str, set[str]] = {}

    for config in sorted(configs, key=lambda c: c.priority):
        if config.disabled:
            continue
        contributions.setdefault(config.package_name, set())
        for table in _manifest_tables(config.manifest_path):
            owner = owners.get(table)
            if owner is None:
                owners[table] = config
                contributions[config.package_name].add(table)
            elif table in config.overrides:
                contributions[owner.package_name].discard(table)
                owners[table] = config
                contributions[config.package_name].add(table)
            elif table in config.merge_tables or table in owner.merge_tables:
                contributions[config.package_name].add(table)
            # else: registration already rejected this overlap; keep owner.

    return contributions


@dataclass
class TenantFilter:
    """
    Filter which tenants a batch seed applies to.

    Attributes:
        include: Only these tenant ids (UUID or string).
        exclude: Skip these tenant ids.
        predicate: Optional extra ``predicate(tenant) -> bool``.
    """

    include: list[Any] | None = None
    exclude: list[Any] | None = None
    predicate: Callable[[Tenant], bool] | None = None

    @staticmethod
    def _as_ids(values: list[Any] | None) -> set[UUID] | None:
        if values is None:
            return None
        return {value if isinstance(value, UUID) else UUID(str(value)) for value in values}

    def allows(self, tenant: Tenant) -> bool:
        included = self._as_ids(self.include)
        excluded = self._as_ids(self.exclude)
        if included is not None and tenant.id not in included:
            return False
        if excluded is not None and tenant.id in excluded:
            return False
        if self.predicate is not None and not self.predicate(tenant):
            return False
        return True


class TenantSeederOrchestrator:
    """
    Seeds tenant databases from every registered tenant seeder package.

    Example:
        >>> orchestrator = TenantSeederOrchestrator(profile="dev")
        >>> result = await orchestrator.seed_tenant(tenant_id)
        >>> summary = await orchestrator.seed_all_tenants(tenant_filter=...)
    """

    def __init__(
        self,
        profile: str = "dev",
        *,
        config: TenantSeederConfig | None = None,
        configs: list[TenantSeederConfig] | None = None,
        strict: bool | None = None,
        on_failure: str | None = None,
        include_packages: list[str] | None = None,
        exclude_packages: list[str] | None = None,
    ) -> None:
        if configs is not None:
            selected = list(configs)
        elif config is not None:
            selected = [config]
        else:
            selected = get_registered_tenant_packages() or [get_seeder_config()]

        if include_packages:
            selected = [c for c in selected if c.package_name in include_packages]
        if exclude_packages:
            selected = [c for c in selected if c.package_name not in exclude_packages]

        self.configs = selected
        self.config = selected[0] if selected else get_seeder_config()
        self.profile = profile
        self.strict = strict
        self.on_failure = on_failure

    def build_engine(self, tenant_id: UUID, config: TenantSeederConfig | None = None) -> SeederEngine:
        """Build a SeederEngine bound to a specific tenant database."""
        chosen = config or self.config
        return SeederEngine(
            manifest_path=chosen.manifest_path,
            model_registry=chosen.model_registry,
            profile=self.profile,
            database_factory=lambda _name: get_tenant_engine(tenant_id),
            strict=self.strict,
            on_failure=self.on_failure,
        )

    async def seed_tenant(
        self,
        tenant_id: UUID,
        *,
        profile: str | None = None,
        layer: str = "boot",
    ) -> SeedingResult:
        """Seed one tenant with every effective package contribution."""
        if profile is not None:
            self.profile = profile

        combined = SeedingResult(
            database_name=f"tenant_{tenant_id}", profile=self.profile, success=True
        )
        contributions = _resolve_tenant_tables(self.configs)

        for config in sorted(self.configs, key=lambda c: c.priority):
            if config.disabled:
                continue
            allowed = contributions.get(config.package_name, set())
            if not allowed:
                continue

            engine = self.build_engine(tenant_id, config)

            # Migrate this package's existing ids to its literals first.
            try:
                session = await get_tenant_session(tenant_id)
                async with session:
                    await adopt_explicit_ids(session, engine, layer=layer)
                    await session.commit()
            except Exception as exc:  # noqa: BLE001 - reported per package
                logger.exception("Explicit-id adoption failed for %s", config.package_name)
                combined.errors.append(f"{config.package_name}: adoption failed: {exc}")
                combined.success = False
                continue

            all_tables = _manifest_tables(config.manifest_path)
            filters = (
                SeederFilters(tables=sorted(allowed))
                if allowed != all_tables
                else None
            )
            try:
                result = await engine.seed(
                    f"tenant_{tenant_id}", filters=filters, layer=layer
                )
            except Exception as exc:  # noqa: BLE001 - reported per package
                combined.errors.append(f"{config.package_name}: {exc}")
                combined.success = False
                continue

            combined.tables_seeded += result.tables_seeded
            combined.rows_inserted += result.rows_inserted
            combined.rows_updated += result.rows_updated
            combined.rows_skipped += result.rows_skipped
            combined.errors.extend(result.errors)
            combined.success = combined.success and result.success

        return combined

    async def seed_new_tenant(
        self,
        tenant_id: UUID,
        *,
        profile: str | None = None,
    ) -> SeedingResult:
        """Seed boot data for a tenant created at runtime."""
        return await self.seed_tenant(tenant_id, profile=profile, layer="boot")

    async def seed_all_tenants(
        self,
        *,
        tenant_filter: TenantFilter | None = None,
        profile: str | None = None,
        layer: str = "boot",
        active_only: bool = True,
    ) -> dict[str, Any]:
        """Seed every (active) tenant, optionally filtered."""
        if profile is not None:
            self.profile = profile

        summary: dict[str, Any] = {
            "profile": self.profile,
            "total_tenants": 0,
            "succeeded": 0,
            "failed": 0,
            "results": [],
        }

        from pgsqlasync2fast_fastapi.connection import get_manager

        auth_engine = get_manager().get_engine(self.config.connection)
        async with AsyncSession(auth_engine) as session:
            stmt = select(Tenant)
            if active_only:
                stmt = active_only_query(stmt)
            tenants = list((await session.execute(stmt)).scalars().all())

        if tenant_filter is not None:
            tenants = [tenant for tenant in tenants if tenant_filter.allows(tenant)]

        summary["total_tenants"] = len(tenants)

        for tenant in tenants:
            result = await self.seed_tenant(tenant.id, layer=layer)
            if result.success:
                summary["succeeded"] += 1
                summary["results"].append(
                    {
                        "tenant_id": str(tenant.id),
                        "status": "succeeded",
                        "rows_seeded": result.rows_inserted + result.rows_updated,
                    }
                )
            else:
                summary["failed"] += 1
                summary["results"].append(
                    {
                        "tenant_id": str(tenant.id),
                        "status": "failed",
                        "errors": result.errors,
                    }
                )

        return summary


async def adopt_explicit_seed_ids(
    session: AsyncSession,
    profile: str = "dev",
    *,
    config: TenantSeederConfig | None = None,
    dry_run: bool = False,
) -> list[Any]:
    """Rewrite a tenant's ids to the literals of one package config."""
    chosen = config or get_seeder_config()
    engine = SeederEngine(
        manifest_path=chosen.manifest_path,
        model_registry=chosen.model_registry,
        profile=profile,
    )
    return await adopt_explicit_ids(session, engine, layer="boot", dry_run=dry_run)


async def adopt_explicit_seed_ids_for_tenant(
    tenant_id: UUID,
    profile: str = "dev",
    *,
    config: TenantSeederConfig | None = None,
    dry_run: bool = False,
) -> list[Any]:
    """Open a tenant session and adopt explicit ids for one package config."""
    session = await get_tenant_session(tenant_id)
    async with session:
        remaps = await adopt_explicit_seed_ids(
            session, profile=profile, config=config, dry_run=dry_run
        )
        if not dry_run:
            await session.commit()
        return remaps


# The package's own RBAC seeders are the base contribution.
register_tenant_package_seeders(get_seeder_config())


__all__ = [
    "TENANT_RBAC_MANIFEST_PATH",
    "TENANT_RBAC_MODEL_REGISTRY",
    "TenantSeederConfig",
    "TenantSeederConflictError",
    "TenantFilter",
    "TenantSeederOrchestrator",
    "get_seeder_config",
    "register_tenant_package_seeders",
    "get_registered_tenant_packages",
    "clear_tenant_package_registry",
    "set_tenant_package_enabled",
    "disable_tenant_package_seeders",
    "enable_tenant_package_seeders",
    "adopt_explicit_seed_ids",
    "adopt_explicit_seed_ids_for_tenant",
]
