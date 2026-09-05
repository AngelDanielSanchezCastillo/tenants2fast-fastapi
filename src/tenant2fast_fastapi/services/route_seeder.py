"""
TENANT route+link seeder (tenants2fast-fastapi).

RBAC standardization D2: the TENANT route / permission_routes / role inserter
lives here so a client (app) manifest of guarded routes is seeded into each
per-tenant DB idempotently, instead of the app hand-rolling its own inserter.

TENANT rules:
- Route natural key is ``path`` + ``method``.
- cover-all routes (no explicit roles) default to the tenant OWNER role.
- explicit roles are honored when declared.
- profile-aware: dev-only routes are excluded when running ``prod``.
- idempotent via the shared ``pgsqlasync2fast.insert_if_missing`` primitive.

This module follows the package's per-tenant seeder pattern and does NOT use
``register_seeder`` (tenant seeders are driven per-tenant / per DB).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pgsqlasync2fast_fastapi.seeder import insert_if_missing

from tenant2fast_fastapi.models.assignments_model import PermissionRoute
from tenant2fast_fastapi.models.permission_model import Permission
from tenant2fast_fastapi.models.role_model import Role
from tenant2fast_fastapi.models.route_model import Route

# Cover-all semantics (spec v3): a tenant route without explicit roles is
# implicitly granted to the tenant OWNER role.
DEFAULT_TENANT_ROLE = "OWNER"


@dataclass(frozen=True, slots=True)
class RouteSpec:
    """Declares ONE guarded TENANT route for seeding."""

    method: str
    path: str
    permission: str | None = None
    roles: list[str] = field(default_factory=list)
    profile: set[str] = field(default_factory=lambda: {"dev", "prod"})


async def seed_tenant_routes(
    session,
    manifest: list[RouteSpec],
    profile: str = "prod",
) -> dict[str, int]:
    """
    Seed TENANT routes, permission_routes and roles idempotently.

    Args:
        session: SQLModel AsyncSession bound to ONE tenant DB.
        manifest: list of RouteSpec to consider.
        profile: active profile; specs whose ``profile`` does not contain it
            are skipped.

    Returns:
        A summary dict: ``{"tenant_routes", "tenant_links", "tenant_roles",
        "errors"}`` counts.
    """
    summary: dict[str, int] = {
        "tenant_routes": 0,
        "tenant_links": 0,
        "tenant_roles": 0,
        "errors": 0,
    }

    for spec in manifest:
        if profile not in spec.profile:
            continue
        try:
            await _seed_tenant_route(session, spec)
            summary["tenant_routes"] += 1
            if spec.permission:
                summary["tenant_links"] += 1
            summary["tenant_roles"] += len(_effective_roles(spec))
        except Exception:
            summary["errors"] += 1

    return summary


def _effective_roles(spec: RouteSpec) -> list[str]:
    """Cover-all tenant routes default to OWNER; otherwise the explicit roles."""
    if not spec.roles:
        return [DEFAULT_TENANT_ROLE]
    return list(spec.roles)


async def _seed_tenant_route(session, spec: RouteSpec) -> None:
    """Insert/update one TENANT route (route + permission link + roles)."""
    route = await insert_if_missing(
        session,
        Route,
        lookup={"path": spec.path, "method": spec.method},
        defaults={"description": f"{spec.method} {spec.path}"},
    )

    if spec.permission:
        permission = await insert_if_missing(
            session,
            Permission,
            lookup={"name": spec.permission},
            defaults={"is_active": True},
        )
        await insert_if_missing(
            session,
            PermissionRoute,
            lookup={"permission_id": permission.id, "route_id": route.id},
        )

    for role_name in _effective_roles(spec):
        await insert_if_missing(
            session,
            Role,
            lookup={"name": role_name},
            defaults={"is_active": True},
        )
