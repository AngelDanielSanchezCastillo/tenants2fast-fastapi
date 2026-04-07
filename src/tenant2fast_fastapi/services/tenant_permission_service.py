from typing import List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from rbac2fast_core.protocols.models import (
    PermissionCategoryProtocol,
    PermissionProtocol,
    PermissionAssignmentProtocol,
    PermissionRouteProtocol
)
from rbac2fast_core.protocols.services import PermissionServiceProtocol
from ..models.permission_category_model import TenantPermissionCategory
from ..models.permission_model import TenantPermission
from ..models.assignments_model import TenantUserPermission, TenantPermissionRoute
from ..models.route_model import TenantRoute


class TenantPermissionService(PermissionServiceProtocol):
    """
    Service for managing permissions and categories within a tenant.
    Implements rbac2fast-core PermissionServiceProtocol.
    """

    async def create_category(
        self, category_data: Any, session: AsyncSession
    ) -> TenantPermissionCategory:
        """Create a new permission category."""
        category = TenantPermissionCategory(**category_data.model_dump())
        session.add(category)
        await session.commit()
        await session.refresh(category)
        return category

    async def list_categories(
        self, session: AsyncSession, skip: int = 0, limit: int = 100
    ) -> List[TenantPermissionCategory]:
        """List all permission categories."""
        result = await session.execute(select(TenantPermissionCategory).offset(skip).limit(limit))
        return list(result.scalars().all())

    async def create_permission(
        self, permission_data: Any, session: AsyncSession
    ) -> TenantPermission:
        """Create a new permission."""
        permission = TenantPermission(**permission_data.model_dump())
        session.add(permission)
        await session.commit()
        await session.refresh(permission)
        return permission

    async def get_permission(
        self, permission_id: int, session: AsyncSession
    ) -> Optional[TenantPermission]:
        """Get permission by ID."""
        result = await session.execute(select(TenantPermission).where(TenantPermission.id == permission_id))
        return result.scalar_one_or_none()

    async def list_permissions(
        self, session: AsyncSession, skip: int = 0, limit: int = 100
    ) -> List[TenantPermission]:
        """List all permissions in the tenant."""
        result = await session.execute(select(TenantPermission).offset(skip).limit(limit))
        return list(result.scalars().all())

    async def update_permission(
        self, permission_id: int, permission_data: Any, session: AsyncSession
    ) -> Optional[TenantPermission]:
        """Update a permission's metadata."""
        permission = await self.get_permission(permission_id, session)
        if not permission:
            return None
        
        update_data = permission_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(permission, key, value)
            
        session.add(permission)
        await session.commit()
        await session.refresh(permission)
        return permission

    async def delete_permission(
        self, permission_id: int, session: AsyncSession
    ) -> bool:
        """Permanently delete a permission."""
        permission = await self.get_permission(permission_id, session)
        if not permission:
            return False
            
        await session.delete(permission)
        await session.commit()
        return True

    async def add_permission_route(
        self, permission_id: int, route_id: int, session: AsyncSession
    ) -> TenantPermissionRoute:
        """Protect a route with a permission."""
        assignment = TenantPermissionRoute(permission_id=permission_id, route_id=route_id)
        session.add(assignment)
        await session.commit()
        await session.refresh(assignment)
        return assignment

    async def assign_user_permission(
        self, user_id: int, permission_id: int, session: AsyncSession
    ) -> TenantUserPermission:
        """Directly assign a permission to a tenant user (override)."""
        assignment = TenantUserPermission(user_id=user_id, permission_id=permission_id, is_allowed=True)
        session.add(assignment)
        await session.commit()
        await session.refresh(assignment)
        return assignment

    async def list_user_permissions(
        self, user_id: int, session: AsyncSession
    ) -> List[TenantPermission]:
        """List all permissions directly assigned to a tenant user."""
        result = await session.execute(
            select(TenantPermission)
            .join(TenantUserPermission)
            .where(TenantUserPermission.user_id == user_id)
        )
        return list(result.scalars().all())

    async def remove_user_permission(
        self, user_id: int, permission_id: int, session: AsyncSession
    ) -> bool:
        """Remove a direct permission assignment from a tenant user."""
        result = await session.execute(
            select(TenantUserPermission).where(
                TenantUserPermission.user_id == user_id,
                TenantUserPermission.permission_id == permission_id
            )
        )
        assignment = result.scalar_one_or_none()
        if not assignment:
            return False
            
        await session.delete(assignment)
        await session.commit()
        return True


# Instantiate the service
tenant_permission_service = TenantPermissionService()
