from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from tools2fast_fastapi import APIResponse

from ..dependencies import get_current_tenant, has_tenant_permission
from ..models import Tenant
from ..schemas.rbac.role_schema import (
    TenantRoleRead,
    TenantRoleCreate,
    TenantRoleUpdate
)
from ..schemas.response_schemas import (
    TenantRoleCreatedResponse,
    TenantRoleListResponse,
    TenantRoleSingleResponse,
    TenantRoleResponse,
    TenantRoleErrorResponse,
    NoContentResponse,
)
from ..settings import settings
from ..services.tenant_role_service import tenant_role_service
from ..databases.tenant_db_factory import get_tenant_session


# Ensure prefix starts with "/"
prefix = settings.url_prefix.get_secret_value()
if not prefix.startswith("/"):
    prefix = f"/{prefix}"

tenant_roles_router = APIRouter(
    prefix=prefix+"/roles",
    tags=["Tenants Roles"],
)


@tenant_roles_router.post(
    "/",
    response_model=TenantRoleCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(has_tenant_permission("/roles", "POST"))]
)
async def create_role(
    role_data: TenantRoleCreate,
    tenant: Tenant = Depends(get_current_tenant)
) -> TenantRoleCreatedResponse:
    """Create a new role in the tenant."""
    async with await get_tenant_session(tenant.id) as session:
        role = await tenant_role_service.create_role(role_data, session)
        return TenantRoleCreatedResponse(
            role=TenantRoleResponse(
                id=role.id,
                name=role.name,
                description=role.description,
                is_active=role.is_active,
                created_at=role.created_at,
                updated_at=role.updated_at,
            )
        )


@tenant_roles_router.get(
    "/",
    response_model=TenantRoleListResponse,
    dependencies=[Depends(has_tenant_permission("/roles", "GET"))]
)
async def list_roles(
    skip: int = 0,
    limit: int = 100,
    tenant: Tenant = Depends(get_current_tenant)
) -> TenantRoleListResponse:
    """List all available roles in the tenant."""
    async with await get_tenant_session(tenant.id) as session:
        roles = await tenant_role_service.list_roles(session, skip, limit)
        return TenantRoleListResponse(
            roles=[
                TenantRoleResponse(
                    id=r.id,
                    name=r.name,
                    description=r.description,
                    is_active=r.is_active,
                    created_at=r.created_at,
                    updated_at=r.updated_at,
                )
                for r in roles
            ],
            count=len(roles),
        )


@tenant_roles_router.get(
    "/{role_id}",
    response_model=TenantRoleSingleResponse,
    dependencies=[Depends(has_tenant_permission("/roles/{role_id}", "GET"))],
    responses={404: {"model": TenantRoleErrorResponse}},
)
async def get_role(
    role_id: int,
    tenant: Tenant = Depends(get_current_tenant)
) -> JSONResponse | TenantRoleSingleResponse:
    """Get a specific role by ID."""
    async with await get_tenant_session(tenant.id) as session:
        role = await tenant_role_service.get_role_by_id(role_id, session)
        if not role:
            error_resp, http_status = APIResponse.fail(
                message="Role not found",
                status_code=404,
            )
            return JSONResponse(status_code=http_status, content=error_resp.model_dump())
        return TenantRoleSingleResponse(
            role=TenantRoleResponse(
                id=role.id,
                name=role.name,
                description=role.description,
                is_active=role.is_active,
                created_at=role.created_at,
                updated_at=role.updated_at,
            )
        )


@tenant_roles_router.patch(
    "/{role_id}",
    response_model=TenantRoleSingleResponse,
    dependencies=[Depends(has_tenant_permission("/roles/{role_id}", "PATCH"))]
)
async def update_role(
    role_id: int,
    role_data: TenantRoleUpdate,
    tenant: Tenant = Depends(get_current_tenant)
) -> TenantRoleSingleResponse:
    """Update a role's metadata or permissions."""
    async with await get_tenant_session(tenant.id) as session:
        role = await tenant_role_service.update_role(role_id, role_data, session)
        return TenantRoleSingleResponse(
            role=TenantRoleResponse(
                id=role.id,
                name=role.name,
                description=role.description,
                is_active=role.is_active,
                created_at=role.created_at,
                updated_at=role.updated_at,
            )
        )


@tenant_roles_router.delete(
    "/{role_id}",
    response_model=NoContentResponse,
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(has_tenant_permission("/roles/{role_id}", "DELETE"))]
)
async def delete_role(
    role_id: int,
    tenant: Tenant = Depends(get_current_tenant)
) -> None:
    """Delete a role from the tenant."""
    async with await get_tenant_session(tenant.id) as session:
        await tenant_role_service.delete_role(role_id, session)
