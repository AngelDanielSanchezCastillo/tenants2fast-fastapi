from typing import List, Optional, Any
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from rbac2fast_core.protocols.models import RoleProtocol, UserRoleProtocol, PermissionAssignmentProtocol
from rbac2fast_core.protocols.services import RoleServiceProtocol
from ..models.role_model import Role
from ..models.assignments_model import RoleUser, PermissionRole
from ..models.user_model import User
from ..models.permission_model import Permission


class TenantRoleService(RoleServiceProtocol):
    """
    Service for managing roles within a tenant.
    Implements rbac2fast-core RoleServiceProtocol.
    """

    async def create_role(self, role_data: Any, session: AsyncSession) -> Role:
        """Create a new role."""
        role = Role(**role_data.model_dump())
        session.add(role)
        await session.commit()
        await session.refresh(role)
        return role

    async def get_role(self, role_id: int, session: AsyncSession) -> Optional[Role]:
        """Get role by ID."""
        result = await session.exec(select(Role).where(Role.id == role_id))
        return result.one_or_none()

    async def list_roles(
        self, session: AsyncSession, skip: int = 0, limit: int = 100
    ) -> List[Role]:
        """List all roles in the tenant."""
        result = await session.exec(select(Role).offset(skip).limit(limit))
        return list(result.all())

    async def update_role(
        self, role_id: int, role_data: Any, session: AsyncSession
    ) -> Optional[Role]:
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
    ) -> PermissionRole:
        """Assign a permission to a role."""
        assignment = PermissionRole(role_id=role_id, permission_id=permission_id)
        session.add(assignment)
        await session.commit()
        await session.refresh(assignment)
        return assignment

    async def list_role_permissions(
        self, role_id: int, session: AsyncSession
    ) -> List[Permission]:
        """List all permissions assigned to a role."""
        result = await session.exec(select(Permission)
            .join(PermissionRole)
            .where(PermissionRole.role_id == role_id)
        )
        return list(result.all())

    async def delete_role_permission(
        self, role_id: int, permission_id: int, session: AsyncSession
    ) -> bool:
        """Remove a permission from a role."""
        result = await session.exec(select(PermissionRole).where(
                PermissionRole.role_id == role_id,
                PermissionRole.permission_id == permission_id
            )
        )
        assignment = result.one_or_none()
        if not assignment:
            return False
            
        await session.delete(assignment)
        await session.commit()
        return True

    async def assign_user_role(
        self, user_id: int, role_id: int, session: AsyncSession
    ) -> RoleUser:
        """Assign a role to a user."""
        assignment = RoleUser(user_id=user_id, role_id=role_id)
        session.add(assignment)
        await session.commit()
        await session.refresh(assignment)
        return assignment

    async def list_user_roles(
        self, user_id: int, session: AsyncSession
    ) -> List[Role]:
        """List all roles assigned to a user."""
        result = await session.exec(select(Role)
            .join(RoleUser)
            .where(RoleUser.user_id == user_id)
        )
        return list(result.all())

    async def remove_user_role(
        self, user_id: int, role_id: int, session: AsyncSession
    ) -> bool:
        """Remove a role from a user."""
        result = await session.exec(select(RoleUser).where(
                RoleUser.user_id == user_id,
                RoleUser.role_id == role_id
            )
        )
        assignment = result.one_or_none()
        if not assignment:
            return False
            
        await session.delete(assignment)
        await session.commit()
        return True


# Instantiate the service
tenant_role_service = TenantRoleService()
