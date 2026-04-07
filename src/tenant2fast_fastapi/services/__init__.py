"""Services for tenant2fast-fastapi"""

from .tenant_service import (
    create_tenant,
    get_tenant_by_id,
    get_tenant_by_slug,
    list_tenants,
    update_tenant,
    deactivate_tenant,
    delete_tenant_permanently,
)
from .tenant_user_service import (
    add_user_to_tenant,
    get_tenant_user,
    get_tenant_user_by_auth_id,
    list_tenant_users,
    update_tenant_user,
    remove_user_from_tenant,
)
from .tenant_role_service import tenant_role_service
from .tenant_permission_service import tenant_permission_service
from .tenant_access_service import tenant_access_service
from .tenant_rbac_seeder import seed_tenant_rbac

__all__ = [
    "create_tenant",
    "get_tenant_by_id",
    "get_tenant_by_slug",
    "list_tenants",
    "update_tenant",
    "deactivate_tenant",
    "delete_tenant_permanently",
    "add_user_to_tenant",
    "get_tenant_user",
    "get_tenant_user_by_auth_id",
    "list_tenant_users",
    "update_tenant_user",
    "remove_user_from_tenant",
    "tenant_role_service",
    "tenant_permission_service",
    "tenant_access_service",
    "seed_tenant_rbac",
]
