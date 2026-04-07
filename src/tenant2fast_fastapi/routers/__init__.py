"""Routers for tenant2fast-fastapi"""

from fastapi import APIRouter
from .tenants_router import router as tenants_router
from .tenant_users_router import router as tenant_users_router
from .tenant_roles_router import router as tenant_roles_router
from .tenant_permissions_router import router as tenant_permissions_router

def get_tenant_routers() -> APIRouter:
    """Helper to get a combined router with all tenant-related endpoints."""
    main_router = APIRouter()
    main_router.include_router(tenants_router)
    main_router.include_router(tenant_users_router)
    main_router.include_router(tenant_roles_router)
    main_router.include_router(tenant_permissions_router)
    return main_router

__all__ = [
    "tenants_router",
    "tenant_users_router",
    "tenant_roles_router",
    "tenant_permissions_router",
    "get_tenant_routers",
]
