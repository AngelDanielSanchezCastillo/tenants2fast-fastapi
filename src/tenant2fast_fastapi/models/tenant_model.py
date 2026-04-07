from datetime import datetime

from sqlmodel import BigInteger, Column, Field, SQLModel

from oauth2fast_fastapi.models.bases import AuthModel


# Tenant2 model - stores information about each client/organization
class Tenant(AuthModel, table=True):
    __tablename__ = "tenants"

    id: int = Field(
        default=None, sa_column=Column(BigInteger, index=True, primary_key=True)
    )
    name: str = Field(index=True)  # Company/client name
    slug: str = Field(unique=True, index=True)  # URL-friendly identifier
    database_name: str = Field(unique=True, index=True)  # Name of the tenant's database
    is_active: bool = Field(default=True)  # Enable/disable tenant

    # Optional metadata
    contact_email: str | None = Field(default=None)
    max_users: int | None = Field(default=None)  # Optional user limit per tenant


# Pydantic model for API responses (without timestamps from mixin)
class TenantRead(SQLModel):
    id: int
    name: str
    slug: str
    database_name: str
    is_active: bool
    contact_email: str | None = None
    max_users: int | None = None
    created_at: datetime
    updated_at: datetime
