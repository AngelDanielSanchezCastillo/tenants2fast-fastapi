import re
from typing import List, Optional, Any
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from rbac2fast_core.protocols.services import AccessServiceProtocol
from ..models.user_model import User
from ..models.role_model import Role
from ..models.permission_model import Permission
from ..models.route_model import Route
from ..models.assignments_model import (
    RoleUser,
    PermissionRole,
    PermissionUser,
    PermissionRoute
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
        1. Obtener User (copia local)
        2. PermissionUser override (is_allowed=True -> allow, is_allowed=False -> deny)
        3. PermissionRole (por roles del usuario)
        4. deny por defecto
        """
        # 1. Get User ID
        result = await session.exec(select(User.id).where(User.auth_user_id == auth_user_id)
        )
        tenant_user_id = result.one_or_none()
        if not tenant_user_id:
            return False

        # 2. Get all permissions for this user (including overrides and roles)
        permissions = await self.get_user_permissions(tenant_user_id, session)
        
        # 3. Evaluate access against permissions
        return self.evaluate_route_access(permissions, route_path, method)

    async def get_user_permissions(self, tenant_user_id: int, session: AsyncSession) -> List[dict]:
        """
        Resolve all permissions for a user.
        Returns a list of permission objects with their associated routes.
        """
        # 1. Direct overrides (PermissionUser)
        result = await session.exec(select(Permission, PermissionUser.is_allowed)
            .join(PermissionUser)
            .where(PermissionUser.user_id == tenant_user_id)
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
        result = await session.exec(select(Permission)
            .join(PermissionRole)
            .join(RoleUser, PermissionRole.role_id == RoleUser.role_id)
            .where(RoleUser.user_id == tenant_user_id)
        )
        role_perms = []
        for perm in result.all():
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
        result = await session.exec(select(Route)
            .join(PermissionRoute)
            .where(PermissionRoute.permission_id == permission_id)
        )
        return [
            {"path": r.path, "method": r.method} for r in result.all()
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
