from sqlmodel import Field
from .bases import TenantBaseModel


class Role(TenantBaseModel, table=True):
    """
    Role associated with a tenant.
    """

    __tablename__ = "roles"

    name: str = Field(unique=True, index=True)
    description: str | None = Field(default=None)
    is_active: bool = Field(default=True)
