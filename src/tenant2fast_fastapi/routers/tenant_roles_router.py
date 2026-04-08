from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..dependencies import get_current_tenant, has_tenant_permission
from ..models import Tenant
from ..schemas.rbac.role_schema import (
    TenantRoleRead,
    TenantRoleCreate,
    TenantRoleUpdate
)
from ..services.tenant_role_service import tenant_role_service
from ..databases.tenant_db_factory import get_tenant_session


router = APIRouter(prefix="/roles", tags=["Tenant Roles"])

@router.post(
    "/",
    response_model=TenantRoleRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(has_tenant_permission("/roles", "POST"))]
)
async def create_role(
    role_data: TenantRoleCreate,
    tenant: Tenant = Depends(get_current_tenant)
):
    """Create a new role in the tenant."""
    async with await get_tenant_session(tenant.id) as session:
        return await tenant_role_service.create_role(role_data, session)


@router.get(
    "/",
    response_model=list[TenantRoleRead],
    dependencies=[Depends(has_tenant_permission("/roles", "GET"))]
)
async def list_roles(
    skip: int = 0,
    limit: int = 100,
    tenant: Tenant = Depends(get_current_tenant)
):
    """List all available roles in the tenant."""
    async with await get_tenant_session(tenant.id) as session:
        return await tenant_role_service.list_roles(session, skip, limit)


@router.get(
    "/{role_id}",
    response_model=TenantRoleRead,
    dependencies=[Depends(has_tenant_permission("/roles/{role_id}", "GET"))]
)
async def get_role(
    role_id: int,
    tenant: Tenant = Depends(get_current_tenant)
):
    """Get a specific role by ID."""
    async with await get_tenant_session(tenant.id) as session:
        role = await tenant_role_service.get_role_by_id(role_id, session)
        if not role:
            raise HTTPException(status_code=404, detail="Role not found")
        return role


@router.patch(
    "/{role_id}",
    response_model=TenantRoleRead,
    dependencies=[Depends(has_tenant_permission("/roles/{role_id}", "PATCH"))]
)
async def update_role(
    role_id: int,
    role_data: TenantRoleUpdate,
    tenant: Tenant = Depends(get_current_tenant)
):
    """Update a role's metadata or permissions."""
    async with await get_tenant_session(tenant.id) as session:
        return await tenant_role_service.update_role(role_id, role_data, session)


@router.delete(
    "/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(has_tenant_permission("/roles/{role_id}", "DELETE"))]
)
async def delete_role(
    role_id: int,
    tenant: Tenant = Depends(get_current_tenant)
):
    """Delete a role from the tenant."""
    async with await get_tenant_session(tenant.id) as session:
        await tenant_role_service.delete_role(role_id, session)
