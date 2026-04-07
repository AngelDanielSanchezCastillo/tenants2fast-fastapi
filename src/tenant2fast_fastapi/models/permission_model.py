from sqlmodel import Field
from .bases import TenantBaseModel


class TenantPermission(TenantBaseModel, table=True):
    """
    Permission associated with a category.
    """

    __tablename__ = "tenant_permissions"

    name: str = Field(unique=True, index=True)
    permission_category_id: int = Field(foreign_key="tenant_permission_categories.id")
