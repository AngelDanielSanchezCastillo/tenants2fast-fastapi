"""
tenant2fast-fastapi

Multi-tenancy system for FastAPI applications.
Provides tenant management, user-tenant relationships, and tenant isolation.
"""

from .__version__ import __version__
from .models.tenant_model import Tenant, TenantRead
from .middleware.tenant_middleware import TenantMiddleware
from .dependencies import (
    get_current_tenant,
    get_current_user,
    require_tenant_permission,
    get_current_tenant_user,
    load_tenant_by_id,
)
from .databases.tenant_db_factory import (
    create_tenant_database,
    get_tenant_engine,
    initialize_tenant_schema,
)

__all__ = [
    "__version__",
    "Tenant",
    "TenantRead",
    "TenantMiddleware",
    "get_current_tenant",
    "get_current_user",
    "require_tenant_permission",
    "get_current_tenant_user",
    "load_tenant_by_id",
    "create_tenant_database",
    "get_tenant_engine",
    "initialize_tenant_schema",
]

