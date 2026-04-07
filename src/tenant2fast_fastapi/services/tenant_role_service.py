from typing import List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from rbac2fast_core.protocols.models import RoleProtocol, UserRoleProtocol, PermissionAssignmentProtocol
from rbac2fast_core.protocols.services import RoleServiceProtocol
from ..models.role_model import TenantRole
from ..models.assignments_model import TenantUserRole, TenantRolePermission
from ..models.tenant_user_model import TenantUser
from ..models.permission_model import TenantPermission


class TenantRoleService(RoleServiceProtocol):
    """
    Service for managing roles within a tenant.
    Implements rbac2fast-core RoleServiceProtocol.
    """

    async def create_role(self, role_data: Any, session: AsyncSession) -> TenantRole:
        """Create a new role."""
        role = TenantRole(**role_data.model_dump())
        session.add(role)
        await session.commit()
        await session.refresh(role)
        return role

    async def get_role(self, role_id: int, session: AsyncSession) -> Optional[TenantRole]:
        """Get role by ID."""
        result = await session.execute(select(TenantRole).where(TenantRole.id == role_id))
        return result.scalar_one_or_none()

    async def list_roles(
        self, session: AsyncSession, skip: int = 0, limit: int = 100
    ) -> List[TenantRole]:
        """List all roles in the tenant."""
        result = await session.execute(select(TenantRole).offset(skip).limit(limit))
        return list(result.scalars().all())

    async def update_role(
        self, role_id: int, role_data: Any, session: AsyncSession
    ) -> Optional[TenantRole]:
        """Update a role's metadata."""
        role = await self.get_role(role_id, session)
        if not role:
            return None
        
        update_data = role_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(role, key, value)
            
        session.add(role)
        await session.commit()
        await session.refresh(role)
        return role

    async def delete_role(self, role_id: int, session: AsyncSession) -> bool:
        """Permanently delete a role."""
        role = await self.get_role(role_id, session)
        if not role:
            return False
        
        await session.delete(role)
        await session.commit()
        return True

    async def add_role_permission(
        self, role_id: int, permission_id: int, session: AsyncSession
    ) -> TenantRolePermission:
        """Assign a permission to a role."""
        assignment = TenantRolePermission(role_id=role_id, permission_id=permission_id)
        session.add(assignment)
        await session.commit()
        await session.refresh(assignment)
        return assignment

    async def list_role_permissions(
        self, role_id: int, session: AsyncSession
    ) -> List[TenantPermission]:
        """List all permissions assigned to a role."""
        result = await session.execute(
            select(TenantPermission)
            .join(TenantRolePermission)
            .where(TenantRolePermission.role_id == role_id)
        )
        return list(result.scalars().all())

    async def delete_role_permission(
        self, role_id: int, permission_id: int, session: AsyncSession
    ) -> bool:
        """Remove a permission from a role."""
        result = await session.execute(
            select(TenantRolePermission).where(
                TenantRolePermission.role_id == role_id,
                TenantRolePermission.permission_id == permission_id
            )
        )
        assignment = result.scalar_one_or_none()
        if not assignment:
            return False
            
        await session.delete(assignment)
        await session.commit()
        return True

    async def assign_user_role(
        self, user_id: int, role_id: int, session: AsyncSession
    ) -> TenantUserRole:
        """Assign a role to a tenant user."""
        assignment = TenantUserRole(user_id=user_id, role_id=role_id)
        session.add(assignment)
        await session.commit()
        await session.refresh(assignment)
        return assignment

    async def list_user_roles(
        self, user_id: int, session: AsyncSession
    ) -> List[TenantRole]:
        """List all roles assigned to a tenant user."""
        result = await session.execute(
            select(TenantRole)
            .join(TenantUserRole)
            .where(TenantUserRole.user_id == user_id)
        )
        return list(result.scalars().all())

    async def remove_user_role(
        self, user_id: int, role_id: int, session: AsyncSession
    ) -> bool:
        """Remove a role from a tenant user."""
        result = await session.execute(
            select(TenantUserRole).where(
                TenantUserRole.user_id == user_id,
                TenantUserRole.role_id == role_id
            )
        )
        assignment = result.scalar_one_or_none()
        if not assignment:
            return False
            
        await session.delete(assignment)
        await session.commit()
        return True


# Instantiate the service
tenant_role_service = TenantRoleService()
