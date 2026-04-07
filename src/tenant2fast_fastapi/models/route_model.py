from sqlmodel import Field
from .bases import TenantBaseModel


class TenantRoute(TenantBaseModel, table=True):
    """
    Route that can be protected.
    """

    __tablename__ = "tenant_routes"

    name: str
    path: str = Field(index=True)   # ej: "/reports/{id}"
    method: str = Field(default="*") # GET, POST, * ...
    is_active: bool = Field(default=True)
