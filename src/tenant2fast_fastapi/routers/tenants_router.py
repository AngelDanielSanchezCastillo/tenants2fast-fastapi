"""
Tenant Router

API endpoints for tenant management (admin only).
"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from ..schemas.tenant_schema import TenantCreate, TenantList, TenantRead, TenantUpdate
from ..services import tenant_service

router = APIRouter(prefix="/tenants", tags=["Tenants"])


@router.post(
    "",
    # response_model=TenantRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create new tenant",
    description="Create a new tenant with dedicated database. Requires admin privileges.",
)
async def create_tenant(tenant_data: TenantCreate):
    """
    Create a new tenant.

    This will:
    1. Create tenant record in auth database
    2. Create dedicated PostgreSQL database
    3. Initialize schema in tenant database
    4. Cache tenant data in Redis
    """
    tenant = await tenant_service.create_tenant(tenant_data)
    return tenant


@router.get(
    "/{tenant_id}",
    # response_model=TenantRead,
    summary="Get tenant by ID",
    description="Retrieve tenant information by ID.",
)
async def get_current_tenant(tenant_id: int):
    """Get tenant by ID."""
    tenant = await tenant_service.get_tenant_by_id(tenant_id)

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant {tenant_id} not found",
        )

    return tenant


@router.get(
    "/slug/{slug}",
    # response_model=TenantRead,
    summary="Get tenant by slug",
    description="Retrieve tenant information by slug.",
)
async def get_tenant_by_slug(slug: str):
    """Get tenant by slug."""
    tenant = await tenant_service.get_tenant_by_slug(slug)

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant with slug '{slug}' not found",
        )

    return tenant


@router.get(
    "",
    response_model=TenantList,
    summary="List all tenants",
    description="List all tenants with pagination.",
)
async def list_tenants(
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
):
    """List all tenants with pagination."""
    tenants, total = await tenant_service.list_tenants(skip=skip, limit=limit)

    return TenantList(
        tenants=tenants,
        total=total,
    )


@router.put(
    "/{tenant_id}",
    # response_model=TenantRead,
    summary="Update tenant",
    description="Update tenant metadata. Cannot change slug or database_name.",
)
async def update_tenant(tenant_id: int, tenant_data: TenantUpdate):
    """Update tenant metadata."""
    tenant = await tenant_service.update_tenant(tenant_id, tenant_data)
    return tenant



@router.delete(
    "/{tenant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate tenant",
    description="Deactivate a tenant (soft delete). Tenant can be reactivated later.",
)
async def deactivate_tenant(tenant_id: int):
    """Deactivate a tenant (soft delete)."""
    await tenant_service.deactivate_tenant(tenant_id)


@router.delete(
    "/{tenant_id}/permanent",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete tenant",
    description="⚠️ DANGER: Permanently delete tenant and their database. This cannot be undone!",
)
async def delete_tenant_permanently(
    tenant_id: int, confirm: Annotated[bool, Query()] = False
):
    """
    Permanently delete a tenant and their database.

    ⚠️ WARNING: This action cannot be undone!
    All data for this tenant will be permanently lost.

    You must pass `confirm=true` as a query parameter.
    """
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must confirm deletion by passing confirm=true",
        )

    await tenant_service.delete_tenant_permanently(tenant_id)
