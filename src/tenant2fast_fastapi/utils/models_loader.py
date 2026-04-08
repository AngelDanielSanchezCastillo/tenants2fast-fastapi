"""
Models Loader Utility

Central place to import all models to ensure they register with SQLAlchemy/SQLModel metadata.
"""

def import_tenant_models():
    """Import all models that belong to the tenant-specific metadata."""
    from ..models.tenant_user_model import TenantUser
    from ..models.role_model import TenantRole
    from ..models.permission_model import TenantPermission
    from ..models.route_model import TenantRoute
    from ..models.assignments_model import (
        TenantUserRole, 
        TenantRolePermission,
        TenantPermissionRoute,
        TenantUserPermission
    )
    # Add any other tenant-specific models here


def import_auth_models():
    """Import all models that belong to the Auth/Global metadata."""
    from ..models.tenant_model import Tenant
    from ..models.user_tenant_model import UserTenant
