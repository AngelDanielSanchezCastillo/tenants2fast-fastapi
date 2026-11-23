"""
Tenant Router

API endpoints for tenant management (admin only).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status
from fastapi.responses import JSONResponse

from tools2fast_fastapi import APIResponse

from ..settings import settings
from ..schemas.tenant_schema import TenantCreate, TenantList, TenantUpdate
from ..schemas.response_schemas import (
    TenantCreatedResponse,
    TenantListResponse,
    TenantSingleResponse,
    TenantResponse,
    TenantErrorResponse,
    DeleteSuccessResponse,
    DeleteErrorResponse,
    NoContentResponse,
)
from ..services import tenant_service

# Ensure prefix starts with "/"
prefix = settings.url_prefix.get_secret_value()
if not prefix.startswith("/"):
    prefix = f"/{prefix}"

tenants_router = APIRouter(
    prefix=prefix,
    tags=[prefix.strip("/").capitalize()],
)


def _tenant_response(tenant) -> TenantResponse:
    """Build a TenantResponse from a Tenant model."""
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        database_name=tenant.database_name,
        contact_email=tenant.contact_email,
        max_users=tenant.max_users,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
        deleted_at=tenant.deleted_at,
        deleted_by=tenant.deleted_by,
    )


@tenants_router.post(
    "",
    response_model=TenantCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new tenant",
    description="Create a new tenant with dedicated database. Requires admin privileges.",
)
async def create_tenant(tenant_data: TenantCreate) -> TenantCreatedResponse:
    """
    Create a new tenant.

    This will:
    1. Create tenant record in auth database
    2. Create dedicated PostgreSQL database
    3. Initialize schema in tenant database
    4. Cache tenant data in Redis
    """
    tenant = await tenant_service.create_tenant(tenant_data)
    return TenantCreatedResponse(tenant=_tenant_response(tenant))


@tenants_router.get(
    "/{tenant_id}",
    response_model=TenantSingleResponse,
    summary="Get tenant by ID",
    description="Retrieve tenant information by ID.",
    responses={404: {"model": TenantErrorResponse}},
)
async def get_current_tenant(tenant_id: UUID) -> JSONResponse | TenantSingleResponse:
    """Get tenant by ID."""
    tenant = await tenant_service.get_tenant_by_id(tenant_id)

    if not tenant:
        error_resp, http_status = APIResponse.fail(
            message=f"Tenant {tenant_id} not found",
            status_code=404,
        )
        return JSONResponse(status_code=http_status, content=error_resp.model_dump())

    return TenantSingleResponse(tenant=_tenant_response(tenant))


@tenants_router.get(
    "/slug/{slug}",
    response_model=TenantSingleResponse,
    summary="Get tenant by slug",
    description="Retrieve tenant information by slug.",
    responses={404: {"model": TenantErrorResponse}},
)
async def get_tenant_by_slug(slug: str) -> JSONResponse | TenantSingleResponse:
    """Get tenant by slug."""
    tenant = await tenant_service.get_tenant_by_slug(slug)

    if not tenant:
        error_resp, http_status = APIResponse.fail(
            message=f"Tenant with slug '{slug}' not found",
            status_code=404,
        )
        return JSONResponse(status_code=http_status, content=error_resp.model_dump())

    return TenantSingleResponse(tenant=_tenant_response(tenant))


@tenants_router.get(
    "",
    response_model=TenantListResponse,
    summary="List all tenants",
    description="List all tenants with pagination.",
)
async def list_tenants(
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> TenantListResponse:
    """List all tenants with pagination."""
    tenants, total = await tenant_service.list_tenants(skip=skip, limit=limit)

    return TenantListResponse(
        tenants=[_tenant_response(t) for t in tenants],
        total=total,
        count=len(tenants),
    )


@tenants_router.put(
    "/{tenant_id}",
    response_model=TenantSingleResponse,
    summary="Update tenant",
    description="Update tenant metadata. Cannot change slug or database_name.",
)
async def update_tenant(tenant_id: UUID, tenant_data: TenantUpdate) -> TenantSingleResponse:
    """Update tenant metadata."""
    tenant = await tenant_service.update_tenant(tenant_id, tenant_data)
    return TenantSingleResponse(tenant=_tenant_response(tenant))


@tenants_router.delete(
    "/{tenant_id}",
    response_model=DeleteSuccessResponse,
    summary="Soft-delete tenant",
    description="Soft-delete a tenant. Tenant can be restored later via restore().",
)
async def deactivate_tenant(tenant_id: UUID) -> DeleteSuccessResponse:
    """Soft-delete a tenant."""
    await tenant_service.deactivate_tenant(tenant_id)
    return DeleteSuccessResponse()


@tenants_router.delete(
    "/{tenant_id}/permanent",
    response_model=None,
    summary="Permanently delete tenant",
    description="⚠️ DANGER: Permanently delete tenant and their database. This cannot be undone!",
)
async def delete_tenant_permanently(
    tenant_id: UUID, confirm: Annotated[bool, Query()] = False
) -> JSONResponse | None:
    """
    Permanently delete a tenant and their database.

    ⚠️ WARNING: This action cannot be undone!
    All data for this tenant will be permanently lost.

    You must pass `confirm=true` as a query parameter.
    """
    if not confirm:
        error_resp, http_status = APIResponse.fail(
            message="You must confirm deletion by passing confirm=true",
            status_code=400,
        )
        return JSONResponse(status_code=http_status, content=error_resp.model_dump())

    await tenant_service.delete_tenant_permanently(tenant_id)
