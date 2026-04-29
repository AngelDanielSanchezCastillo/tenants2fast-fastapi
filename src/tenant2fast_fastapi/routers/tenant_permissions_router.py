from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from tools2fast_fastapi import APIResponse

from ..dependencies import get_current_tenant, has_tenant_permission
from ..models import Tenant
from ..schemas.rbac.permission_schema import TenantPermissionRead
from ..schemas.response_schemas import (
    TenantPermissionListResponse,
    TenantPermissionSingleResponse,
    TenantPermissionResponse,
    TenantPermissionCategoryListResponse,
    TenantPermissionCategoryResponse,
    TenantPermissionErrorResponse,
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
    response_model=TenantPermissionListResponse,
    dependencies=[Depends(has_tenant_permission("/permissions", "GET"))]
)
async def list_permissions(
    tenant: Tenant = Depends(get_current_tenant)
) -> TenantPermissionListResponse:
    """List all available permissions in the tenant."""
    async with await get_tenant_session(tenant.id) as session:
        permissions = await tenant_permission_service.list_permissions(session)
        return TenantPermissionListResponse(
            permissions=[
                TenantPermissionResponse(
                    id=p.id,
                    name=p.name,
                    permission_category_id=p.permission_category_id,
                )
                for p in permissions
            ],
            count=len(permissions),
        )


@tenant_permissions_router.get(
    "/categories",
    response_model=TenantPermissionCategoryListResponse,
    dependencies=[Depends(has_tenant_permission("/permissions/categories", "GET"))]
)
async def list_categories(
    tenant: Tenant = Depends(get_current_tenant)
) -> TenantPermissionCategoryListResponse:
    """List all permission categories."""
    async with await get_tenant_session(tenant.id) as session:
        categories = await tenant_permission_service.list_categories(session)
        return TenantPermissionCategoryListResponse(
            categories=[
                TenantPermissionCategoryResponse(
                    id=c.id,
                    name=c.name,
                )
                for c in categories
            ],
            count=len(categories),
        )


@tenant_permissions_router.get(
    "/{permission_id}",
    response_model=TenantPermissionSingleResponse,
    dependencies=[Depends(has_tenant_permission("/permissions/{permission_id}", "GET"))],
    responses={404: {"model": TenantPermissionErrorResponse}},
)
async def get_permission(
    permission_id: int,
    tenant: Tenant = Depends(get_current_tenant)
) -> JSONResponse | TenantPermissionSingleResponse:
    """Get a specific permission by ID."""
    async with await get_tenant_session(tenant.id) as session:
        permission = await tenant_permission_service.get_permission_by_id(permission_id, session)
        if not permission:
            error_resp, http_status = APIResponse.fail(
                message="Permission not found",
                status_code=404,
            )
            return JSONResponse(status_code=http_status, content=error_resp.model_dump())
        return TenantPermissionSingleResponse(
            permission=TenantPermissionResponse(
                id=permission.id,
                name=permission.name,
                permission_category_id=permission.permission_category_id,
            )
        )
