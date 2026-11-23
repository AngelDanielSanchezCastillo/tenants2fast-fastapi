from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TenantUserBase(BaseModel):
    """Base schema for TenantUser."""
    auth_user_id: UUID
    position: str | None = None
    department: str | None = None
    is_admin: bool = False

    model_config = ConfigDict(from_attributes=True)


class TenantUserCreate(TenantUserBase):
    """Schema to create a TenantUser."""
    pass


class TenantUserRead(TenantUserBase):
    """Schema to read a TenantUser."""
    id: UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    deleted_by: UUID | None = None


class TenantUserUpdate(BaseModel):
    """Schema to update a TenantUser."""
    position: str | None = None
    department: str | None = None
    is_admin: bool | None = None

    model_config = ConfigDict(from_attributes=True)
