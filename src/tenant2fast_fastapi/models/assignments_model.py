from sqlmodel import Field
from .bases import TenantBaseModel


class TenantUserRole(TenantBaseModel, table=True):
    """
    Many-to-many relationship between users and roles in a tenant.
    """

    __tablename__ = "tenant_user_roles"

    user_id: int = Field(foreign_key="tenant_users.id", index=True)
    role_id: int = Field(foreign_key="tenant_roles.id", index=True)


class TenantRolePermission(TenantBaseModel, table=True):
    """
    Many-to-many relationship between roles and permissions.
    """

    __tablename__ = "tenant_role_permissions"

    role_id: int = Field(foreign_key="tenant_roles.id", index=True)
    permission_id: int = Field(foreign_key="tenant_permissions.id", index=True)


class TenantUserPermission(TenantBaseModel, table=True):
    """
    Direct assignment of permissions to users (overrides).
    """

    __tablename__ = "tenant_user_permissions"

    user_id: int = Field(foreign_key="tenant_users.id", index=True)
    permission_id: int = Field(foreign_key="tenant_permissions.id", index=True)
    is_allowed: bool = Field(default=True)


class TenantPermissionRoute(TenantBaseModel, table=True):
    """
    Mapping between permissions and the routes they protect.
    """

    __tablename__ = "tenant_permission_routes"

    permission_id: int = Field(foreign_key="tenant_permissions.id", index=True)
    route_id: int = Field(foreign_key="tenant_routes.id", index=True)
