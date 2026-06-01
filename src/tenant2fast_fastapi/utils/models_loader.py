"""
Models Loader Utility

Central place to import all models to ensure they register with SQLAlchemy/SQLModel metadata.
"""

def import_tenant_models():
    """Import all models that belong to the tenant-specific metadata."""
    from ..models.user_model import User
    from ..models.role_model import Role
    from ..models.permission_model import Permission
    from ..models.route_model import Route
    from ..models.assignments_model import (
        RoleUser, 
        PermissionRole,
        PermissionRoute,
        PermissionUser
    )
    # Add any other tenant-specific models here


def import_auth_models():
    """Import all models that belong to the Auth/Global metadata."""
    from ..models.tenant_model import Tenant
    from ..models.user_tenant_model import TenantUser
