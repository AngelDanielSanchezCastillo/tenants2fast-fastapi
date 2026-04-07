"""Schemas for tenant2fast-fastapi"""

from .tenant_schema import (
    TenantCreate,
    TenantUpdate,
    TenantRead,
    TenantList,
)

from .rbac import (
    TenantRoleCreate,
    TenantRoleRead,
    TenantRoleUpdate,
    TenantPermissionCategoryCreate,
    TenantPermissionCategoryRead,
    TenantPermissionCreate,
    TenantPermissionRead,
    TenantPermissionUpdate,
    TenantUserCreate,
    TenantUserRead,
    TenantUserUpdate,
)

__all__ = [
    "TenantCreate",
    "TenantUpdate",
    "TenantRead",
    "TenantList",
    "TenantRoleCreate",
    "TenantRoleRead",
    "TenantRoleUpdate",
    "TenantPermissionCategoryCreate",
    "TenantPermissionCategoryRead",
    "TenantPermissionCreate",
    "TenantPermissionRead",
    "TenantPermissionUpdate",
    "TenantUserCreate",
    "TenantUserRead",
    "TenantUserUpdate",
]
