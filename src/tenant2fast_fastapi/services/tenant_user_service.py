from fastapi import HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from oauth2fast_fastapi import get_auth_session
from pgsqlasync2fast_fastapi.connection import get_manager
from oauth2fast_fastapi.models.user_model import User as AuthUser
from ..models.tenant_user_model import TenantUser
from ..models.user_tenant_model import UserTenant
from ..schemas.rbac.user_schema import TenantUserCreate, TenantUserUpdate


async def add_user_to_tenant(
    tenant_id: int, user_data: TenantUserCreate, tenant_session: AsyncSession
) -> TenantUser:
    """
    Add a user to a tenant.
    
    1. Validates that the user exists in the Auth database.
    2. Creates a TenantUser record in the tenant's database.
    3. Creates a UserTenant mapping in the Auth database (membership).
    """
    async with await get_manager().get_session("auth") as auth_session:
        # 1. Validate user exists in Auth
        result = await auth_session.exec(select(AuthUser).where(AuthUser.id == user_data.auth_user_id)
        )
        auth_user = result.one_or_none()
        
        if not auth_user:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"User with ID {user_data.auth_user_id} not found in auth system",
            )
            
        # 2. Check if already in tenant (membership record)
        result = await auth_session.exec(select(UserTenant).where(
                UserTenant.tenant_id == tenant_id,
                UserTenant.user_id == user_data.auth_user_id
            )
        )
        if result.one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already a member of this tenant",
            )

        # 3. Create TenantUser in tenant DB
        tenant_user = TenantUser(
            auth_user_id=user_data.auth_user_id,
            position=user_data.position,
            department=user_data.department,
            is_admin=user_data.is_admin,
        )
        tenant_session.add(tenant_user)
        await tenant_session.commit()
        await tenant_session.refresh(tenant_user)
        
        # 4. Create UserTenant in Auth DB
        membership = UserTenant(
            user_id=user_data.auth_user_id,
            tenant_id=tenant_id
        )
        auth_session.add(membership)
        await auth_session.commit()
        
        return tenant_user


async def get_tenant_user(user_id: int, session: AsyncSession) -> TenantUser | None:
    """Get a tenant user by their internal ID."""
    result = await session.exec(select(TenantUser).where(TenantUser.id == user_id))
    return result.one_or_none()


async def get_tenant_user_by_auth_id(auth_user_id: int, session: AsyncSession) -> TenantUser | None:
    """Get a tenant user by their Auth user ID."""
    result = await session.exec(select(TenantUser).where(TenantUser.auth_user_id == auth_user_id)
    )
    return result.one_or_none()


async def list_tenant_users(
    session: AsyncSession, skip: int = 0, limit: int = 100
) -> list[TenantUser]:
    """List all users in the tenant."""
    result = await session.exec(select(TenantUser).offset(skip).limit(limit)
    )
    return list(result.all())


async def update_tenant_user(
    user_id: int, user_data: TenantUserUpdate, session: AsyncSession
) -> TenantUser:
    """Update tenant user metadata."""
    tenant_user = await get_tenant_user(user_id, session)
    if not tenant_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant user {user_id} not found"
        )

    # Only update fields that exist in TenantUser model
    update_data = user_data.model_dump(exclude_unset=True)
    valid_fields = {'position', 'department', 'is_admin', 'is_active'}
    for key, value in update_data.items():
        if key in valid_fields:
            setattr(tenant_user, key, value)

    session.add(tenant_user)
    await session.commit()
    await session.refresh(tenant_user)
    return tenant_user


async def remove_user_from_tenant(
    tenant_id: int, auth_user_id: int, tenant_session: AsyncSession
):
    """
    Remove a user from a tenant.
    
    1. Deletes TenantUser from tenant DB.
    2. Deletes UserTenant mapping from Auth DB.
    """
    # 1. Delete from tenant DB
    tenant_user = await get_tenant_user_by_auth_id(auth_user_id, tenant_session)
    if tenant_user:
        await tenant_session.delete(tenant_user)
        await tenant_session.commit()
        
    # 2. Delete from Auth DB
    async with await get_manager().get_session("auth") as auth_session:
        result = await auth_session.exec(select(UserTenant).where(
                UserTenant.tenant_id == tenant_id,
                UserTenant.user_id == auth_user_id
            )
        )
        membership = result.one_or_none()
        if membership:
            await auth_session.delete(membership)
            await auth_session.commit()
