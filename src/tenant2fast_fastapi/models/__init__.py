"""Models for tenant2fast-fastapi"""

from .tenant_model import Tenant, TenantRead
from .user_tenant_model import TenantUser  # Mapping in Auth DB (users ↔ tenants)
from .user_model import User  # Local user in Tenant DB
from .role_model import Role
from .permission_category_model import Category
from .permission_model import Permission
from .route_model import Route
from .assignments_model import (
    RoleUser,
    PermissionRole,
    PermissionRoute,
    PermissionUser,
)

__all__ = [
    "Tenant",
    "TenantRead",
    "TenantUser",  # Mapping in Auth DB (users ↔ tenants)
    "User",  # Local user in Tenant DB
    "Role",
    "Category",
    "Permission",
    "Route",
    "RoleUser",
    "PermissionRole",
    "PermissionRoute",
    "PermissionUser",
]
