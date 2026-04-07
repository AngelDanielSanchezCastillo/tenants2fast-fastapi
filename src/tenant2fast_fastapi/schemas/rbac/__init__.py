"""RBAC schemas for tenants2fast-fastapi"""

from .role_schema import (
    TenantRoleCreate,
    TenantRoleRead,
    TenantRoleUpdate,
)
from .permission_schema import (
    TenantPermissionCategoryCreate,
    TenantPermissionCategoryRead,
    TenantPermissionCreate,
    TenantPermissionRead,
    TenantPermissionUpdate,
)
from .user_schema import (
    TenantUserCreate,
    TenantUserRead,
    TenantUserUpdate,
)

__all__ = [
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
