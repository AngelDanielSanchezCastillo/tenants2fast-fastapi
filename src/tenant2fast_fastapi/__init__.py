"""
tenant2fast-fastapi

Multi-tenancy system for FastAPI applications.
Provides tenant management, user-tenant relationships, and tenant isolation.
"""

# Register the tenant2fast-auth and tenant2fast-rbac Alembic chains under the
# "auth" and "tenant" lanes at import time (mirrors the register_seeder idiom;
# alembic-2fast change).
from . import migrations as _migrations  # noqa: F401
from .__version__ import __version__
from .databases.tenant_db_factory import (
    create_tenant_database,
    get_tenant_engine,
    initialize_tenant_schema,
)
from .dependencies import (
    get_current_tenant,
    get_current_tenant_user,
    get_current_user,
    get_tenant_context,
    get_tenant_db_session,
    get_user_context,
    has_tenant_permission,
    has_tenant_role,
    load_tenant_by_id,
    require_tenant_owner,
    set_tenant_context,
    set_user_context,
)
from .middleware.tenant_middleware import TenantMiddleware
from .models.bases import TenantAuditBaseModel, TenantBaseModel
from .models.tenant_model import Tenant, TenantRead

# TENANT route+link seeding (RBAC standardization D2)
from .services.route_seeder import RouteSpec, seed_tenant_routes

# Tenant seeders do NOT use register_seeder() because:
# 1. They don't seed the auth connection directly
# 2. They seed dynamic tenant_N connections
# 3. seed_all_tenants() handles the iteration over all tenants
# Instead, tenants2fast-fastapi exposes seed_all_tenants() for explicit calling
# after tenant creation or for bulk re-seeding
from .services.tenant_rbac_seeder import (
    get_seeder_config,
    reseed_all_rbac,
    seed,
    seed_all_tenants,
    seed_tenant_rbac,
)

__all__ = [
    "__version__",
    "Tenant",
    "TenantRead",
    "TenantAuditBaseModel",
    "TenantBaseModel",
    "TenantMiddleware",
    "get_current_tenant",
    "get_current_user",
    "has_tenant_permission",
    "has_tenant_role",
    "get_current_tenant_user",
    "require_tenant_owner",
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
    "reseed_all_rbac",
    # TENANT route+link seeding (RBAC standardization D2)
    "RouteSpec",
    "seed_tenant_routes",
]