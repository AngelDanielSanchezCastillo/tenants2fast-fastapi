import re
from typing import List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from rbac2fast_core.protocols.services import AccessServiceProtocol
from ..models.tenant_user_model import TenantUser
from ..models.role_model import TenantRole
from ..models.permission_model import TenantPermission
from ..models.route_model import TenantRoute
from ..models.assignments_model import (
    TenantUserRole,
    TenantRolePermission,
    TenantUserPermission,
    TenantPermissionRoute
)


class TenantAccessService(AccessServiceProtocol):
    """
    Service for checking user access within a tenant.
    Implements rbac2fast-core AccessServiceProtocol.
    """

    async def check_user_access(
        self, auth_user_id: int, route_path: str, method: str, session: AsyncSession
    ) -> bool:
        """
        Check if a user has access to a specific route.
        Lógica de resolución:
        1. Obtener TenantUser (copia local)
        2. TenantUserPermission override (is_allowed=True -> allow, is_allowed=False -> deny)
        3. TenantRolePermission (por roles del usuario)
        4. deny por defecto
        """
        # 1. Get TenantUser ID
        result = await session.execute(
            select(TenantUser.id).where(TenantUser.auth_user_id == auth_user_id)
        )
        tenant_user_id = result.scalar_one_or_none()
        if not tenant_user_id:
            return False

        # 2. Get all permissions for this user (including overrides and roles)
        permissions = await self.get_user_permissions(tenant_user_id, session)
        
        # 3. Evaluate access against permissions
        return self.evaluate_route_access(permissions, route_path, method)

    async def get_user_permissions(self, tenant_user_id: int, session: AsyncSession) -> List[dict]:
        """
        Resolve all permissions for a tenant user.
        Returns a list of permission objects with their associated routes.
        """
        # 1. Direct overrides (UserPermission)
        result = await session.execute(
            select(TenantPermission, TenantUserPermission.is_allowed)
            .join(TenantUserPermission)
            .where(TenantUserPermission.user_id == tenant_user_id)
        )
        direct_perms = []
        for perm, is_allowed in result.all():
            routes = await self._get_permission_routes(perm.id, session)
            direct_perms.append({
                "id": perm.id,
                "name": perm.name,
                "is_allowed": is_allowed,
                "routes": routes
            })

        # 2. Role permissions
        result = await session.execute(
            select(TenantPermission)
            .join(TenantRolePermission)
            .join(TenantUserRole, TenantRolePermission.role_id == TenantUserRole.role_id)
            .where(TenantUserRole.user_id == tenant_user_id)
        )
        role_perms = []
        for perm in result.scalars().all():
            routes = await self._get_permission_routes(perm.id, session)
            role_perms.append({
                "id": perm.id,
                "name": perm.name,
                "is_allowed": True,
                "routes": routes
            })

        # Combine: overrides first, then roles
        return direct_perms + role_perms

    async def _get_permission_routes(self, permission_id: int, session: AsyncSession) -> List[dict]:
        """Internal helper to get routes for a permission."""
        result = await session.execute(
            select(TenantRoute)
            .join(TenantPermissionRoute)
            .where(TenantPermissionRoute.permission_id == permission_id)
        )
        return [
            {"path": r.path, "method": r.method} for r in result.scalars().all()
        ]

    def evaluate_route_access(self, resolved_permissions: List[dict], route_path: str, method: str) -> bool:
        """
        Evaluates if any of the permissions allow access to the given path and method.
        Supports route pattern matching with {param}.
        """
        for perm in resolved_permissions:
            # If the permission is explicitly denied by an override, skip this permission
            if not perm["is_allowed"]:
                # However, if it's a direct deny override, we should probably stop evaluating?
                # Usually overrides take absolute precedence.
                # If we find a direct DENY override for a route that matches, return False.
                for route in perm["routes"]:
                    if self._match_route(route["path"], route["method"], route_path, method):
                        return False
                continue

            # If it's an ALLOW permission, check if any route matches
            for route in perm["routes"]:
                if self._match_route(route["path"], route["method"], route_path, method):
                    return True

        return False

    def _match_route(self, pattern: str, pattern_method: str, request_path: str, request_method: str) -> bool:
        """Matches a route pattern with an actual request path and method."""
        # Check method
        if pattern_method != "*" and pattern_method.upper() != request_method.upper():
            return False

        # Convert pattern like "/users/{user_id}/orders" to regex
        # "/users/[^/]+/orders"
        regex_pattern = re.sub(r"\{[a-zA-Z0-9_]+\}", r"[^/]+", pattern)
        regex_pattern = f"^{regex_pattern}$"
        
        return bool(re.match(regex_pattern, request_path))


# Instantiate the service
tenant_access_service = TenantAccessService()
