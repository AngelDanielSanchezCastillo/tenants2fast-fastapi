"""Dependencies for tenant2fast-fastapi"""

from .tenant_context import (
    get_current_tenant,
    get_current_user,
    get_tenant_context,
    get_user_context,
    load_tenant_by_id,
    set_tenant_context,
    set_user_context,
)
from .tenant_rbac import has_tenant_permission, has_tenant_role, get_current_tenant_user

__all__ = [
    "get_current_tenant",
    "get_current_user",
    "get_tenant_context",
    "get_user_context",
    "load_tenant_by_id",
    "has_tenant_permission",
    "has_tenant_role",
    "get_current_tenant_user",
    "set_tenant_context",
    "set_user_context",
]
