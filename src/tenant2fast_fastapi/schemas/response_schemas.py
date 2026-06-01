"""
Response schemas for tenant2fast API endpoints.

These schemas provide unified API response format with success/error patterns.
"""

from datetime import datetime
from typing import Literal
from pydantic import BaseModel

from tools2fast_fastapi import ErrorDetail


# ============ Tenant Responses ============

class TenantResponse(BaseModel):
    """Response for tenant data."""
    id: int
    name: str
    slug: str
    database_name: str
    is_active: bool
    contact_email: str | None = None
    max_users: int | None = None
    created_at: datetime
    updated_at: datetime


class TenantCreatedResponse(BaseModel):
    """Successful tenant creation response."""
    success: Literal[True] = True
    message: str = "Tenant creado exitosamente"
    tenant: TenantResponse


class TenantListResponse(BaseModel):
    """Successful tenant list response."""
    success: Literal[True] = True
    message: str = "Éxito"
    tenants: list[TenantResponse]
    total: int
    count: int


class TenantSingleResponse(BaseModel):
    """Successful single tenant response."""
    success: Literal[True] = True
    message: str = "Éxito"
    tenant: TenantResponse


class TenantErrorResponse(BaseModel):
    """Error response for tenant operations."""
    success: Literal[False] = False
    error_type: Literal["controlled"] = "controlled"
    message: str
    error: ErrorDetail | None = None


class TenantUnexpectedErrorResponse(BaseModel):
    """Unexpected error response for tenant operations."""
    success: Literal[False] = False
    error_type: Literal["unexpected"] = "unexpected"
    message: str = "Ha ocurrido un error"
    error: ErrorDetail | None = None


# ============ User Responses ============

class UserResponse(BaseModel):
    """Response for user data."""
    id: int
    auth_user_id: int
    position: str | None = None
    department: str | None = None
    is_admin: bool = False
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class UserCreatedResponse(BaseModel):
    """Successful user creation response."""
    success: Literal[True] = True
    message: str = "Usuario añadido al tenant exitosamente"
    user: UserResponse


class UserListResponse(BaseModel):
    """Successful user list response."""
    success: Literal[True] = True
    message: str = "Éxito"
    users: list[UserResponse]
    count: int


class UserSingleResponse(BaseModel):
    """Successful single user response."""
    success: Literal[True] = True
    message: str = "Éxito"
    user: UserResponse


class UserErrorResponse(BaseModel):
    """Error response for user operations."""
    success: Literal[False] = False
    error_type: Literal["controlled"] = "controlled"
    message: str
    error: ErrorDetail | None = None


# ============ Permission Responses ============

class PermissionResponse(BaseModel):
    """Response for permission data."""
    id: int
    name: str
    permission_category_id: int


class PermissionListResponse(BaseModel):
    """Successful permission list response."""
    success: Literal[True] = True
    message: str = "Éxito"
    permissions: list[PermissionResponse]
    count: int


class PermissionSingleResponse(BaseModel):
    """Successful single permission response."""
    success: Literal[True] = True
    message: str = "Éxito"
    permission: PermissionResponse


class PermissionErrorResponse(BaseModel):
    """Error response for permission operations."""
    success: Literal[False] = False
    error_type: Literal["controlled"] = "controlled"
    message: str
    error: ErrorDetail | None = None


class CategoryResponse(BaseModel):
    """Response for permission category data."""
    id: int
    name: str


class CategoryListResponse(BaseModel):
    """Successful permission category list response."""
    success: Literal[True] = True
    message: str = "Éxito"
    categories: list[CategoryResponse]
    count: int


# ============ Role Responses ============

class RoleResponse(BaseModel):
    """Response for role data."""
    id: int
    name: str
    description: str | None = None
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RoleCreatedResponse(BaseModel):
    """Successful role creation response."""
    success: Literal[True] = True
    message: str = "Rol creado exitosamente"
    role: RoleResponse


class RoleListResponse(BaseModel):
    """Successful role list response."""
    success: Literal[True] = True
    message: str = "Éxito"
    roles: list[RoleResponse]
    count: int


class RoleSingleResponse(BaseModel):
    """Successful single role response."""
    success: Literal[True] = True
    message: str = "Éxito"
    role: RoleResponse


class RoleErrorResponse(BaseModel):
    """Error response for role operations."""
    success: Literal[False] = False
    error_type: Literal["controlled"] = "controlled"
    message: str
    error: ErrorDetail | None = None


# ============ Delete Responses ============

class DeleteSuccessResponse(BaseModel):
    """Successful deletion response."""
    success: Literal[True] = True
    message: str = "Eliminado exitosamente"


class DeleteErrorResponse(BaseModel):
    """Error response for deletion operations."""
    success: Literal[False] = False
    error_type: Literal["controlled"] = "controlled"
    message: str
    error: ErrorDetail | None = None


# ============ No Content Response ============

class NoContentResponse(BaseModel):
    """No content response for 204 responses."""
    pass
