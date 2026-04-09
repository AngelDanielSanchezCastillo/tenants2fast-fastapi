from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from ..dependencies import get_current_tenant, has_tenant_permission
from ..models import Tenant
from ..schemas.rbac.permission_schema import (
    TenantPermissionRead,
    TenantPermissionCategoryRead
)
from ..settings import settings
from ..services.tenant_permission_service import tenant_permission_service
from ..databases.tenant_db_factory import get_tenant_session



# Ensure prefix starts with "/"
prefix = settings.url_prefix.get_secret_value()
if not prefix.startswith("/"):
    prefix = f"/{prefix}"

tenant_permissions_router = APIRouter(
    prefix=prefix+"/permissions",
    tags=["Tenants Permissions"],
)


@tenant_permissions_router.get(
    "/",
    response_model=list[TenantPermissionRead],
    dependencies=[Depends(has_tenant_permission("/permissions", "GET"))]
)
async def list_permissions(
    tenant: Tenant = Depends(get_current_tenant)
):
    """List all available permissions in the tenant."""
    async with await get_tenant_session(tenant.id) as session:
        return await tenant_permission_service.list_permissions(session)


@tenant_permissions_router.get(
    "/categories",
    # response_model=list[TenantPermissionCategoryRead],
    dependencies=[Depends(has_tenant_permission("/permissions/categories", "GET"))]
)
async def list_categories(
    tenant: Tenant = Depends(get_current_tenant)
):
    """List all permission categories."""
    async with await get_tenant_session(tenant.id) as session:
        return await tenant_permission_service.list_categories(session)


@tenant_permissions_router.get(
    "/{permission_id}",
    response_model=TenantPermissionRead,
    dependencies=[Depends(has_tenant_permission("/permissions/{permission_id}", "GET"))]
)
async def get_permission(
    permission_id: int,
    tenant: Tenant = Depends(get_current_tenant)
):
    """Get a specific permission by ID."""
    async with await get_tenant_session(tenant.id) as session:
        permission = await tenant_permission_service.get_permission_by_id(permission_id, session)
        if not permission:
            raise HTTPException(status_code=404, detail="Permission not found")
        return permission
