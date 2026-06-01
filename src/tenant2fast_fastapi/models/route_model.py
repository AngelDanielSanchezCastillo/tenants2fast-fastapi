from sqlmodel import Field
from .bases import TenantBaseModel


class Route(TenantBaseModel, table=True):
    """
    Route that an application has.
    """

    __tablename__ = "routes"

    path: str = Field(index=True)
    method: str = Field(index=True, default="GET")
    description: str | None = Field(default=None)
