"""RBAC schemas for tenants2fast-fastapi"""

from .role_schema import (
    RoleCreate,
    RoleRead,
    RoleUpdate,
)
from .permission_schema import (
    CategoryCreate,
    CategoryRead,
    PermissionCreate,
    PermissionRead,
    PermissionUpdate,
)
from .user_schema import (
    TenantUserCreate,
    TenantUserRead,
    TenantUserUpdate,
)

__all__ = [
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
