"""Schemas for tenant2fast-fastapi"""

from .tenant_schema import (
    TenantCreate,
    TenantUpdate,
    TenantRead,
    TenantList,
)

from .rbac import (
    RoleCreate,
    RoleRead,
    RoleUpdate,
    CategoryCreate,
    CategoryRead,
    PermissionCreate,
    PermissionRead,
    PermissionUpdate,
    TenantUserCreate,
    TenantUserRead,
    TenantUserUpdate,
)

__all__ = [
    "TenantCreate",
    "TenantUpdate",
    "TenantRead",
    "TenantList",
    "RoleCreate",
    "RoleRead",
    "RoleUpdate",
    "CategoryCreate",
    "CategoryRead",
    "PermissionCreate",
    "PermissionRead",
    "PermissionUpdate",
    "TenantUserCreate",
    "TenantUserRead",
    "TenantUserUpdate",
]
