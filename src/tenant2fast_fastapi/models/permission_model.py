from sqlmodel import Field
from .bases import TenantBaseModel


class Permission(TenantBaseModel, table=True):
    """
    Permission associated with a tenant.
    """

    __tablename__ = "permissions"

    name: str = Field(unique=True, index=True)
    description: str | None = Field(default=None)
    is_active: bool = Field(default=True)
    # Optional category grouping; seeded from the JSON key "category_id"
    # (mapped in tenant_rbac_seeder._seed_table_idempotent). Nullable so
    # permissions without a declared category never break the /permissions
    # list (staging regression: AttributeError/500).
    permission_category_id: int | None = Field(
        default=None, foreign_key="categories.id", index=True
    )
