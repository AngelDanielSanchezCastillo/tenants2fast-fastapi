from sqlmodel import Field
from .bases import TenantBaseModel


class RoleUser(TenantBaseModel, table=True):
    """
    Link between a user and a role.
    """

    __tablename__ = "role_users"

    user_id: int = Field(foreign_key="users.id", index=True)
    role_id: int = Field(foreign_key="roles.id", index=True)


class PermissionRole(TenantBaseModel, table=True):
    """
    Link between a role and a permission.
    """

    __tablename__ = "permission_roles"

    role_id: int = Field(foreign_key="roles.id", index=True)
    permission_id: int = Field(foreign_key="permissions.id", index=True)


class PermissionRoute(TenantBaseModel, table=True):
    """
    Link between a permission and a route.
    """

    __tablename__ = "permission_routes"

    permission_id: int = Field(foreign_key="permissions.id", index=True)
    route_id: int = Field(foreign_key="routes.id", index=True)


class PermissionUser(TenantBaseModel, table=True):
    """
    Direct link between a user and a permission (Allow or Deny).
    This can be used to override roles.
    """

    __tablename__ = "permission_users"

    user_id: int = Field(foreign_key="users.id", index=True)
    permission_id: int = Field(foreign_key="permissions.id", index=True)
    is_allowed: bool = Field(default=True)
