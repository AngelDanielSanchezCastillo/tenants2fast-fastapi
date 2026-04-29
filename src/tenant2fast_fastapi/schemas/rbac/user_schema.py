from pydantic import BaseModel, ConfigDict
from datetime import datetime


class TenantUserBase(BaseModel):
    """Base schema for TenantUser."""
    auth_user_id: int
    position: str | None = None
    department: str | None = None
    is_admin: bool = False

    model_config = ConfigDict(from_attributes=True)


class TenantUserCreate(TenantUserBase):
    """Schema to create a TenantUser."""
    pass


class TenantUserRead(TenantUserBase):
    """Schema to read a TenantUser."""
    id: int
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class TenantUserUpdate(BaseModel):
    """Schema to update a TenantUser."""
    position: str | None = None
    department: str | None = None
    is_admin: bool | None = None
    is_active: bool | None = None

    model_config = ConfigDict(from_attributes=True)
