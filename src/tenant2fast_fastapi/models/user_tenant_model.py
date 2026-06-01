from sqlmodel import BigInteger, Column, Field, ForeignKey

from oauth2fast_fastapi.models.bases import AuthModel


class TenantUser(AuthModel, table=True):
    """
    Many-to-many relationship between users and tenants.
    Allows users to belong to multiple tenants.
    """

    __tablename__ = "tenant_users"

    user_id: int = Field(
        sa_column=Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    )
    tenant_id: int = Field(
        sa_column=Column(BigInteger, ForeignKey("tenants.id", ondelete="CASCADE"))
    )
