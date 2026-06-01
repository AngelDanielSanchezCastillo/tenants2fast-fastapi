from sqlmodel import Field
from .bases import TenantBaseModel


class Permission(TenantBaseModel, table=True):
    """
    Permission associated with a tenant.
    """

    __tablename__ = "permissions"

    name: str = Field(unique=True, index=True)
    description: str | None = Field(default=None)
    is_active: bool = Field(default=True)
