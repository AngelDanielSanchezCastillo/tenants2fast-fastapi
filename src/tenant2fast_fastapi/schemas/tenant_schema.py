"""
Tenant Schemas

Pydantic schemas for tenant API operations.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, ConfigDict


class TenantCreate(BaseModel):
    """Schema for creating a new tenant."""

    name: str = Field(
        ..., min_length=1, max_length=255, description="Company/client name"
    )
    slug: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern="^[a-z0-9-]+$",
        description="URL-friendly identifier (lowercase, numbers, hyphens only)",
    )
    contact_email: str | None = Field(None, description="Contact email for tenant")
    max_users: int | None = Field(None, gt=0, description="Maximum users allowed")

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        """Ensure slug is lowercase and valid."""
        return v.lower().strip()


class TenantUpdate(BaseModel):
    """Schema for updating a tenant."""

    name: str | None = Field(None, min_length=1, max_length=255)
    contact_email: str | None = None
    max_users: int | None = Field(None, gt=0)


class TenantRead(BaseModel):
    """Schema for tenant response."""

    id: UUID
    name: str
    slug: str
    database_name: str
    contact_email: str | None = None
    max_users: int | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    deleted_by: UUID | None = None

    model_config = ConfigDict(from_attributes=True)



class TenantList(BaseModel):
    """Schema for list of tenants."""

    tenants: list[TenantRead]
    total: int
