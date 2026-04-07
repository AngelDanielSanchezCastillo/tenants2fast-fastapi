from rbac2fast_core.schemas import (
    PermissionCategoryCreate,
    PermissionCategoryRead,
    PermissionCreate,
    PermissionRead,
    PermissionUpdate,
)


class TenantPermissionCategoryCreate(PermissionCategoryCreate):
    """Schema to create a tenant permission category."""
    pass


class TenantPermissionCategoryRead(PermissionCategoryRead):
    """Schema to read a tenant permission category."""
    pass


class TenantPermissionCreate(PermissionCreate):
    """Schema to create a tenant permission."""
    pass


class TenantPermissionRead(PermissionRead):
    """Schema to read a tenant permission."""
    pass


class TenantPermissionUpdate(PermissionUpdate):
    """Schema to update a tenant permission."""
    pass
