from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..dependencies import (
    get_current_tenant,
    require_tenant_permission,
    get_current_tenant_user
)
from ..models import Tenant, TenantUser
from ..schemas.rbac.user_schema import (
    TenantUserRead,
    TenantUserCreate,
    TenantUserUpdate
)
from ..services import tenant_user_service
from ..databases.tenant_db_factory import get_tenant_session


router = APIRouter(prefix="/users", tags=["Tenant Users"])


@router.post(
    "/",
    response_model=TenantUserRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_tenant_permission("/users", "POST"))]
)
async def add_user(
    user_data: TenantUserCreate,
    tenant: Tenant = Depends(get_current_tenant)
):
    """Add a user to the current tenant."""
    async with await get_tenant_session(tenant.id) as session:
        return await tenant_user_service.add_user_to_tenant(user_data, session)


@router.get(
    "/",
    response_model=list[TenantUserRead],
    dependencies=[Depends(require_tenant_permission("/users", "GET"))]
)
async def list_users(
    skip: int = 0,
    limit: int = 100,
    tenant: Tenant = Depends(get_current_tenant)
):
    """List all users in the current tenant."""
    async with await get_tenant_session(tenant.id) as session:
        return await tenant_user_service.list_tenant_users(session, skip, limit)


@router.get(
    "/me",
    response_model=TenantUserRead
)
async def get_me(
    current_user: TenantUser = Depends(get_current_tenant_user)
):
    """Get the current user's record in the tenant context."""
    return current_user


@router.get(
    "/{user_id}",
    response_model=TenantUserRead,
    dependencies=[Depends(require_tenant_permission("/users/{user_id}", "GET"))]
)
async def get_user(
    user_id: int,
    tenant: Tenant = Depends(get_current_tenant)
):
    """Get a specific user's record."""
    async with await get_tenant_session(tenant.id) as session:
        user = await tenant_user_service.get_tenant_user(user_id, session)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user


@router.patch(
    "/{user_id}",
    response_model=TenantUserRead,
    dependencies=[Depends(require_tenant_permission("/users/{user_id}", "PATCH"))]
)
async def update_user(
    user_id: int,
    user_data: TenantUserUpdate,
    tenant: Tenant = Depends(get_current_tenant)
):
    """Update a user's record or roles."""
    async with await get_tenant_session(tenant.id) as session:
        return await tenant_user_service.update_tenant_user(user_id, user_data, session)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_tenant_permission("/users/{user_id}", "DELETE"))]
)
async def remove_user(
    user_id: int,
    tenant: Tenant = Depends(get_current_tenant)
):
    """Remove a user from the tenant."""
    async with await get_tenant_session(tenant.id) as session:
        await tenant_user_service.remove_user_from_tenant(user_id, session)
