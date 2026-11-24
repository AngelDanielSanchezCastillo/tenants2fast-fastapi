from uuid import UUID

from sqlmodel import Field

from oauth2fast_fastapi.models.bases import AuthSoftDeleteModel


class TenantUser(AuthSoftDeleteModel, table=True):
    """
    Many-to-many relationship between users and tenants.
    Allows users to belong to multiple tenants.
    """

    __tablename__ = "tenant_users"

    user_id: UUID = Field(index=True, foreign_key="users.id")
    tenant_id: UUID = Field(index=True, foreign_key="tenants.id")
