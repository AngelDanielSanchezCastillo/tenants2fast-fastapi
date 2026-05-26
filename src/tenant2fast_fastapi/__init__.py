"""
tenant2fast-fastapi

Multi-tenancy system for FastAPI applications.
Provides tenant management, user-tenant relationships, and tenant isolation.
"""

from .__version__ import __version__
from .models.tenant_model import Tenant, TenantRead
from .middleware.tenant_middleware import TenantMiddleware
from .databases.tenant_db_factory import (
    create_tenant_database,
    get_tenant_engine,
    initialize_tenant_schema,
)
from .dependencies import (
    get_current_tenant,
    get_current_user,
    has_tenant_permission,
    has_tenant_role,
    get_current_tenant_user,
    load_tenant_by_id,
    get_tenant_context,
    get_user_context,
    set_tenant_context,
    set_user_context,
    get_tenant_db_session,
)

# Tenant seeders do NOT use register_seeder() because:
# 1. They don't seed the auth connection directly
# 2. They seed dynamic tenant_N connections
# 3. seed_all_tenants() handles the iteration over all tenants
# Instead, tenants2fast-fastapi exposes seed_all_tenants() for explicit calling
# after tenant creation or for bulk re-seeding

from .services.tenant_rbac_seeder import (
    seed,
    seed_all_tenants,
    get_seeder_config,
    seed_tenant_rbac,
)

__all__ = [
    "__version__",
    "Tenant",
    "TenantRead",
    "TenantMiddleware",
    "get_current_tenant",
    "get_current_user",
    "has_tenant_permission",
    "has_tenant_role",
    "get_current_tenant_user",
    "load_tenant_by_id",
    "get_tenant_context",
    "get_user_context",
    "set_tenant_context",
    "set_user_context",
    "get_tenant_db_session",
    "create_tenant_database",
    "get_tenant_engine",
    "initialize_tenant_schema",
    # Seeder system
    "get_seeder_config",
    "seed",
    "seed_all_tenants",
    "seed_tenant_rbac",
]