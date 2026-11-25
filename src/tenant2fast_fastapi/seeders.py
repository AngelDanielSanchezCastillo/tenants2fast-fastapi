"""
Tenant seeder orchestration (ODD-5).

Wraps pgsqlasync2fast's ``SeederEngine`` to seed tenant databases:
- ``TenantSeederOrchestrator.seed_tenant()``: one tenant
- ``.seed_all_tenants()``: every active tenant (with ``TenantFilter``)
- ``.seed_new_tenant()``: a tenant created at runtime

The package ships explicit uuid7 literals in its manifest; ``natural_key``
upserts keep re-seeding idempotent without duplicating rows. Existing tenant
ids can be migrated to the literals with ``adopt_explicit_seed_ids()``.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Callable
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from tools2fast_fastapi import active_only

from pgsqlasync2fast_fastapi import SeederEngine, SeedingResult, adopt_explicit_ids

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
    """Configuration for the tenant RBAC seeder."""

    manifest_path: str = TENANT_RBAC_MANIFEST_PATH
    model_registry: dict[str, type] = field(
        default_factory=lambda: dict(TENANT_RBAC_MODEL_REGISTRY)
    )
    connection: str = "auth"


def get_seeder_config() -> TenantSeederConfig:
    """Return the tenant seeder configuration (manifest + model registry)."""
    return TenantSeederConfig()


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
    Seeds tenant databases from this package's manifest.

    Example:
        >>> orchestrator = TenantSeederOrchestrator(profile="dev")
        >>> result = await orchestrator.seed_tenant(tenant_id)
        >>> summary = await orchestrator.seed_all_tenants()
    """

    def __init__(
        self,
        profile: str = "dev",
        *,
        config: TenantSeederConfig | None = None,
        strict: bool | None = None,
        on_failure: str | None = None,
    ) -> None:
        self.config = config or get_seeder_config()
        self.profile = profile
        self.strict = strict
        self.on_failure = on_failure

    def build_engine(self, tenant_id: UUID) -> SeederEngine:
        """Build a SeederEngine bound to a specific tenant database."""
        return SeederEngine(
            manifest_path=self.config.manifest_path,
            model_registry=self.config.model_registry,
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
        """Seed one tenant database."""
        if profile is not None:
            self.profile = profile
        return await self.build_engine(tenant_id).seed(
            database_name=f"tenant_{tenant_id}", layer=layer
        )

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
        """
        Seed every (active) tenant, optionally filtered.

        Returns:
            Summary dict ``{profile, total_tenants, succeeded, failed, results}``.
        """
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
                stmt = active_only(stmt)
            tenants = list((await session.execute(stmt)).scalars().all())

        if tenant_filter is not None:
            tenants = [tenant for tenant in tenants if tenant_filter.allows(tenant)]

        summary["total_tenants"] = len(tenants)

        for tenant in tenants:
            try:
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
            except Exception as exc:  # noqa: BLE001 - non-fatal per tenant
                summary["failed"] += 1
                summary["results"].append(
                    {"tenant_id": str(tenant.id), "status": "error", "error": str(exc)}
                )
                logger.exception("Tenant seed failed for %s: %s", tenant.id, exc)

        return summary


async def adopt_explicit_seed_ids(
    session: AsyncSession,
    profile: str = "dev",
    *,
    dry_run: bool = False,
) -> list[Any]:
    """
    Rewrite a tenant's existing RBAC ids to this package's uuid7 literals.

    ``session`` must be bound to the target tenant database. The caller owns
    the transaction (commit when the plan looks right). Idempotent.
    """
    config = get_seeder_config()
    engine = SeederEngine(
        manifest_path=config.manifest_path,
        model_registry=config.model_registry,
        profile=profile,
    )
    return await adopt_explicit_ids(session, engine, layer="boot", dry_run=dry_run)


async def adopt_explicit_seed_ids_for_tenant(
    tenant_id: UUID,
    profile: str = "dev",
    *,
    dry_run: bool = False,
) -> list[Any]:
    """Convenience wrapper: open a tenant session and adopt explicit ids."""
    session = await get_tenant_session(tenant_id)
    async with session:
        remaps = await adopt_explicit_seed_ids(
            session, profile=profile, dry_run=dry_run
        )
        if not dry_run:
            await session.commit()
        return remaps


__all__ = [
    "TENANT_RBAC_MANIFEST_PATH",
    "TENANT_RBAC_MODEL_REGISTRY",
    "TenantSeederConfig",
    "TenantFilter",
    "TenantSeederOrchestrator",
    "get_seeder_config",
    "adopt_explicit_seed_ids",
    "adopt_explicit_seed_ids_for_tenant",
]
