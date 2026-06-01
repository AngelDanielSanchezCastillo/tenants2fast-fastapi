from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from tools2fast_fastapi import APIResponse

from ..dependencies import get_current_tenant, has_tenant_permission
from ..models import Tenant
from ..schemas.rbac.role_schema import (
    RoleRead,
    RoleCreate,
    RoleUpdate
)
from ..schemas.response_schemas import (
    RoleCreatedResponse,
    RoleListResponse,
    RoleSingleResponse,
    RoleResponse,
    RoleErrorResponse,
    DeleteSuccessResponse,
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
    response_model=RoleCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(has_tenant_permission("/roles", "POST"))]
)
async def create_role(
    role_data: RoleCreate,
    tenant: Tenant = Depends(get_current_tenant)
) -> RoleCreatedResponse:
    """Create a new role in the tenant."""
    async with await get_tenant_session(tenant.id) as session:
        role = await tenant_role_service.create_role(role_data, session)
        return RoleCreatedResponse(
            role=RoleResponse(
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
    response_model=RoleListResponse,
    dependencies=[Depends(has_tenant_permission("/roles", "GET"))]
)
async def list_roles(
    skip: int = 0,
    limit: int = 100,
    tenant: Tenant = Depends(get_current_tenant)
) -> RoleListResponse:
    """List all available roles in the tenant."""
    async with await get_tenant_session(tenant.id) as session:
        roles = await tenant_role_service.list_roles(session, skip, limit)
        return RoleListResponse(
            roles=[
                RoleResponse(
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
    response_model=RoleSingleResponse,
    dependencies=[Depends(has_tenant_permission("/roles/{role_id}", "GET"))],
    responses={404: {"model": RoleErrorResponse}},
)
async def get_role(
    role_id: int,
    tenant: Tenant = Depends(get_current_tenant)
) -> JSONResponse | RoleSingleResponse:
    """Get a specific role by ID."""
    async with await get_tenant_session(tenant.id) as session:
        role = await tenant_role_service.get_role_by_id(role_id, session)
        if not role:
            error_resp, http_status = APIResponse.fail(
                message="Role not found",
                status_code=404,
            )
            return JSONResponse(status_code=http_status, content=error_resp.model_dump())
        return RoleSingleResponse(
            role=RoleResponse(
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
    response_model=RoleSingleResponse,
    dependencies=[Depends(has_tenant_permission("/roles/{role_id}", "PATCH"))]
)
async def update_role(
    role_id: int,
    role_data: RoleUpdate,
    tenant: Tenant = Depends(get_current_tenant)
) -> RoleSingleResponse:
    """Update a role's metadata or permissions."""
    async with await get_tenant_session(tenant.id) as session:
        role = await tenant_role_service.update_role(role_id, role_data, session)
        return RoleSingleResponse(
            role=RoleResponse(
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
    response_model=DeleteSuccessResponse,
    dependencies=[Depends(has_tenant_permission("/roles/{role_id}", "DELETE"))]
)
async def delete_role(
    role_id: int,
    tenant: Tenant = Depends(get_current_tenant)
) -> DeleteSuccessResponse:
    """Delete a role from the tenant."""
    async with await get_tenant_session(tenant.id) as session:
        await tenant_role_service.delete_role(role_id, session)
    return DeleteSuccessResponse()
