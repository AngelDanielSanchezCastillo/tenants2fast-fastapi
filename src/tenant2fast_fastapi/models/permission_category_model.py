from sqlmodel import Field
from .bases import TenantBaseModel


class TenantPermissionCategory(TenantBaseModel, table=True):
    """
    Category for grouping permissions.
    """

    __tablename__ = "tenant_permission_categories"

    name: str = Field(unique=True, index=True)
