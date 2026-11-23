from datetime import datetime
from uuid import UUID

from sqlmodel import Field, SQLModel

from oauth2fast_fastapi.models.bases import AuthSoftDeleteModel


# Tenant model - stores information about each client/organization
class Tenant(AuthSoftDeleteModel, table=True):
    __tablename__ = "tenants"

    name: str = Field(index=True)  # Company/client name
    slug: str = Field(unique=True, index=True)  # URL-friendly identifier
    database_name: str = Field(unique=True, index=True)  # Name of the tenant's database
    # is_active removed — soft-delete via SoftDeleteMixin (deleted_at)

    # Optional metadata
    contact_email: str | None = Field(default=None)
    max_users: int | None = Field(default=None)  # Optional user limit per tenant


# Pydantic model for API responses (without timestamps from mixin)
class TenantRead(SQLModel):
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
