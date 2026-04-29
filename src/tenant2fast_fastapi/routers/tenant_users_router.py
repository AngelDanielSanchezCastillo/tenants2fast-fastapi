from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from tools2fast_fastapi import APIResponse

from ..dependencies import (
    get_current_tenant,
    has_tenant_permission,
    get_current_tenant_user
)
from ..models import Tenant, TenantUser
from ..schemas.rbac.user_schema import (
    TenantUserRead,
    TenantUserCreate,
    TenantUserUpdate
)
from ..schemas.response_schemas import (
    TenantUserCreatedResponse,
    TenantUserListResponse,
    TenantUserSingleResponse,
    TenantUserResponse,
    TenantUserErrorResponse,
    NoContentResponse,
)
from ..settings import settings
from ..services import tenant_user_service
from ..databases.tenant_db_factory import get_tenant_session


# Ensure prefix starts with "/"
prefix = settings.url_prefix.get_secret_value()
if not prefix.startswith("/"):
    prefix = f"/{prefix}"

tenant_users_router = APIRouter(
    prefix=prefix+"/users",
    tags=["Tenants Users"],
)


@tenant_users_router.post(
    "/",
    response_model=TenantUserCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(has_tenant_permission("/users", "POST"))]
)
async def add_user(
    user_data: TenantUserCreate,
    tenant: Tenant = Depends(get_current_tenant)
) -> TenantUserCreatedResponse:
    """Add a user to the current tenant."""
    async with await get_tenant_session(tenant.id) as session:
        user = await tenant_user_service.add_user_to_tenant(user_data, session)
        return TenantUserCreatedResponse(
            user=TenantUserResponse(
                id=user.id,
                auth_user_id=user.auth_user_id,
                position=user.position,
                department=user.department,
                internal_email=user.internal_email,
                notes=user.notes,
                is_active_in_tenant=user.is_active_in_tenant,
                created_at=user.created_at,
                updated_at=user.updated_at,
            )
        )


@tenant_users_router.get(
    "/",
    response_model=TenantUserListResponse,
    dependencies=[Depends(has_tenant_permission("/users", "GET"))]
)
async def list_users(
    skip: int = 0,
    limit: int = 100,
    tenant: Tenant = Depends(get_current_tenant)
) -> TenantUserListResponse:
    """List all users in the current tenant."""
    async with await get_tenant_session(tenant.id) as session:
        users = await tenant_user_service.list_tenant_users(session, skip, limit)
        return TenantUserListResponse(
            users=[
                TenantUserResponse(
                    id=u.id,
                    auth_user_id=u.auth_user_id,
                    position=u.position,
                    department=u.department,
                    internal_email=u.internal_email,
                    notes=u.notes,
                    is_active_in_tenant=u.is_active_in_tenant,
                    created_at=u.created_at,
                    updated_at=u.updated_at,
                )
                for u in users
            ],
            count=len(users),
        )


@tenant_users_router.get(
    "/me",
    response_model=TenantUserSingleResponse
)
async def get_me(
    current_user: TenantUser = Depends(get_current_tenant_user)
) -> TenantUserSingleResponse:
    """Get the current user's record in the tenant context."""
    return TenantUserSingleResponse(
        user=TenantUserResponse(
            id=current_user.id,
            auth_user_id=current_user.auth_user_id,
            position=current_user.position,
            department=current_user.department,
            internal_email=current_user.internal_email,
            notes=current_user.notes,
            is_active_in_tenant=current_user.is_active_in_tenant,
            created_at=current_user.created_at,
            updated_at=current_user.updated_at,
        )
    )


@tenant_users_router.get(
    "/{user_id}",
    response_model=TenantUserSingleResponse,
    dependencies=[Depends(has_tenant_permission("/users/{user_id}", "GET"))],
    responses={404: {"model": TenantUserErrorResponse}},
)
async def get_user(
    user_id: int,
    tenant: Tenant = Depends(get_current_tenant)
) -> JSONResponse | TenantUserSingleResponse:
    """Get a specific user's record."""
    async with await get_tenant_session(tenant.id) as session:
        user = await tenant_user_service.get_tenant_user(user_id, session)
        if not user:
            error_resp, http_status = APIResponse.fail(
                message="User not found",
                status_code=404,
            )
            return JSONResponse(status_code=http_status, content=error_resp.model_dump())
        return TenantUserSingleResponse(
            user=TenantUserResponse(
                id=user.id,
                auth_user_id=user.auth_user_id,
                position=user.position,
                department=user.department,
                internal_email=user.internal_email,
                notes=user.notes,
                is_active_in_tenant=user.is_active_in_tenant,
                created_at=user.created_at,
                updated_at=user.updated_at,
            )
        )


@tenant_users_router.patch(
    "/{user_id}",
    response_model=TenantUserSingleResponse,
    dependencies=[Depends(has_tenant_permission("/users/{user_id}", "PATCH"))]
)
async def update_user(
    user_id: int,
    user_data: TenantUserUpdate,
    tenant: Tenant = Depends(get_current_tenant)
) -> TenantUserSingleResponse:
    """Update a user's record or roles."""
    async with await get_tenant_session(tenant.id) as session:
        user = await tenant_user_service.update_tenant_user(user_id, user_data, session)
        return TenantUserSingleResponse(
            user=TenantUserResponse(
                id=user.id,
                auth_user_id=user.auth_user_id,
                position=user.position,
                department=user.department,
                internal_email=user.internal_email,
                notes=user.notes,
                is_active_in_tenant=user.is_active_in_tenant,
                created_at=user.created_at,
                updated_at=user.updated_at,
            )
        )


@tenant_users_router.delete(
    "/{user_id}",
    response_model=NoContentResponse,
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(has_tenant_permission("/users/{user_id}", "DELETE"))]
)
async def remove_user(
    user_id: int,
    tenant: Tenant = Depends(get_current_tenant)
) -> None:
    """Remove a user from the tenant."""
    async with await get_tenant_session(tenant.id) as session:
        await tenant_user_service.remove_user_from_tenant(user_id, session)
