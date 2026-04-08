from sqlmodel import Field
from .bases import TenantBaseModel


class TenantUser(TenantBaseModel, table=True):
    """
    Tenant-specific user information.
    Links a global user (from Auth DB) to a specific tenant.
    """

    __tablename__ = "tenant_users"

    auth_user_id: int = Field(index=True, unique=True)
    
    # Tenant-specific user info
    is_admin: bool = Field(default=False)
    position: str | None = Field(default=None)
    department: str | None = Field(default=None)
    is_active: bool = Field(default=True)
