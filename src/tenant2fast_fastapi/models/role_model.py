from sqlmodel import Field
from .bases import TenantBaseModel


class TenantRole(TenantBaseModel, table=True):
    """
    Role associated with a tenant.
    """

    __tablename__ = "tenant_roles"

    name: str = Field(unique=True, index=True)
    description: str | None = Field(default=None)
    is_active: bool = Field(default=True)
