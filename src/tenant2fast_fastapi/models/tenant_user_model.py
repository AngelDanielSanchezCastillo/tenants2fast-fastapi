from sqlmodel import Field
from .bases import TenantBaseModel


class TenantUser(TenantBaseModel, table=True):
    """
    User record within a specific tenant.
    This is an enriched copy of the global Auth user.
    """

    __tablename__ = "tenant_users"

    # Reference to the user ID in the Auth database
    auth_user_id: int = Field(index=True)

    # Business-specific fields
    position: str | None = Field(default=None)
    department: str | None = None
    internal_email: str | None = Field(default=None)
    notes: str | None = Field(default=None)
    is_active_in_tenant: bool = Field(default=True)
