from sqlmodel import Field
from .bases import TenantBaseModel


class TenantUserRole(TenantBaseModel, table=True):
    """
    Link between a tenant user and a role.
    """

    __tablename__ = "tenant_user_roles"

    user_id: int = Field(foreign_key="tenant_users.id", index=True)
    role_id: int = Field(foreign_key="tenant_roles.id", index=True)


class TenantRolePermission(TenantBaseModel, table=True):
    """
    Link between a role and a permission.
    """

    __tablename__ = "tenant_role_permissions"

    role_id: int = Field(foreign_key="tenant_roles.id", index=True)
    permission_id: int = Field(foreign_key="tenant_permissions.id", index=True)


class TenantPermissionRoute(TenantBaseModel, table=True):
    """
    Link between a permission and a route.
    """

    __tablename__ = "tenant_permission_routes"

    permission_id: int = Field(foreign_key="tenant_permissions.id", index=True)
    route_id: int = Field(foreign_key="tenant_routes.id", index=True)


class TenantUserPermission(TenantBaseModel, table=True):
    """
    Direct link between a tenant user and a permission (Allow or Deny).
    This can be used to override roles.
    """

    __tablename__ = "tenant_user_permissions"

    user_id: int = Field(foreign_key="tenant_users.id", index=True)
    permission_id: int = Field(foreign_key="tenant_permissions.id", index=True)
    is_allowed: bool = Field(default=True)
