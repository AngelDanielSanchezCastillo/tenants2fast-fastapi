from pydantic import BaseModel, ConfigDict
from datetime import datetime


class TenantUserBase(BaseModel):
    """Base schema for TenantUser."""
    auth_user_id: int
    position: str | None = None
    department: str | None = None
    internal_email: str | None = None
    notes: str | None = None
    is_active_in_tenant: bool = True

    model_config = ConfigDict(from_attributes=True)


class TenantUserCreate(TenantUserBase):
    """Schema to create a TenantUser."""
    pass


class TenantUserRead(TenantUserBase):
    """Schema to read a TenantUser."""
    id: int
    created_at: datetime
    updated_at: datetime


class TenantUserUpdate(BaseModel):
    """Schema to update a TenantUser."""
    position: str | None = None
    department: str | None = None
    internal_email: str | None = None
    notes: str | None = None
    is_active_in_tenant: bool | None = None

    model_config = ConfigDict(from_attributes=True)
