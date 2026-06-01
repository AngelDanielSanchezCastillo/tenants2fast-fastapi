from pydantic import ConfigDict
from rbac2fast_core.schemas import (
    PermissionCategoryCreate,
    PermissionCategoryRead,
    PermissionCreate,
    PermissionRead,
    PermissionUpdate,
)


class CategoryCreate(PermissionCategoryCreate):
    """Schema to create a permission category."""
    pass


class CategoryRead(PermissionCategoryRead):
    """Schema to read a permission category."""
    pass

    model_config = ConfigDict(from_attributes=True)


class PermissionCreate(PermissionCreate):
    """Schema to create a permission."""
    pass


class PermissionRead(PermissionRead):
    """Schema to read a permission."""
    pass

    model_config = ConfigDict(from_attributes=True)


class PermissionUpdate(PermissionUpdate):
    """Schema to update a permission."""
    pass
