from sqlmodel import Field
from .bases import TenantBaseModel


class TenantPermission(TenantBaseModel, table=True):
    """
    Permission associated with a tenant.
    """

    __tablename__ = "tenant_permissions"

    name: str = Field(unique=True, index=True)
    description: str | None = Field(default=None)
    is_active: bool = Field(default=True)
