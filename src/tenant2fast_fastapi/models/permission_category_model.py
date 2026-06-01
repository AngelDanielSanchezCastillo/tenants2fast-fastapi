from sqlmodel import Field
from .bases import TenantBaseModel


class Category(TenantBaseModel, table=True):
    """
    Category for grouping permissions.
    """

    __tablename__ = "categories"

    name: str = Field(unique=True, index=True)
