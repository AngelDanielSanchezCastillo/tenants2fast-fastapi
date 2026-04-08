from sqlmodel import Field
from .bases import TenantBaseModel


class TenantRoute(TenantBaseModel, table=True):
    """
    Route that an application has.
    """

    __tablename__ = "tenant_routes"

    path: str = Field(index=True)
    method: str = Field(index=True, default="GET")
    description: str | None = Field(default=None)
