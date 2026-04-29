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


# ============ Tenant User Responses ============

class TenantUserResponse(BaseModel):
    """Response for tenant user data."""
    id: int
    auth_user_id: int
    position: str | None = None
    department: str | None = None
    internal_email: str | None = None
    notes: str | None = None
    is_active_in_tenant: bool = True
    created_at: datetime
    updated_at: datetime


class TenantUserCreatedResponse(BaseModel):
    """Successful tenant user creation response."""
    success: Literal[True] = True
    message: str = "Usuario añadido al tenant exitosamente"
    user: TenantUserResponse


class TenantUserListResponse(BaseModel):
    """Successful tenant user list response."""
    success: Literal[True] = True
    message: str = "Éxito"
    users: list[TenantUserResponse]
    count: int


class TenantUserSingleResponse(BaseModel):
    """Successful single tenant user response."""
    success: Literal[True] = True
    message: str = "Éxito"
    user: TenantUserResponse


class TenantUserErrorResponse(BaseModel):
    """Error response for tenant user operations."""
    success: Literal[False] = False
    error_type: Literal["controlled"] = "controlled"
    message: str
    error: ErrorDetail | None = None


# ============ Tenant Permission Responses ============

class TenantPermissionResponse(BaseModel):
    """Response for tenant permission data."""
    id: int
    name: str
    permission_category_id: int


class TenantPermissionListResponse(BaseModel):
    """Successful tenant permission list response."""
    success: Literal[True] = True
    message: str = "Éxito"
    permissions: list[TenantPermissionResponse]
    count: int


class TenantPermissionSingleResponse(BaseModel):
    """Successful single tenant permission response."""
    success: Literal[True] = True
    message: str = "Éxito"
    permission: TenantPermissionResponse


class TenantPermissionErrorResponse(BaseModel):
    """Error response for tenant permission operations."""
    success: Literal[False] = False
    error_type: Literal["controlled"] = "controlled"
    message: str
    error: ErrorDetail | None = None


class TenantPermissionCategoryResponse(BaseModel):
    """Response for tenant permission category data."""
    id: int
    name: str


class TenantPermissionCategoryListResponse(BaseModel):
    """Successful tenant permission category list response."""
    success: Literal[True] = True
    message: str = "Éxito"
    categories: list[TenantPermissionCategoryResponse]
    count: int


# ============ Tenant Role Responses ============

class TenantRoleResponse(BaseModel):
    """Response for tenant role data."""
    id: int
    name: str
    description: str | None = None
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TenantRoleCreatedResponse(BaseModel):
    """Successful tenant role creation response."""
    success: Literal[True] = True
    message: str = "Rol creado exitosamente"
    role: TenantRoleResponse


class TenantRoleListResponse(BaseModel):
    """Successful tenant role list response."""
    success: Literal[True] = True
    message: str = "Éxito"
    roles: list[TenantRoleResponse]
    count: int


class TenantRoleSingleResponse(BaseModel):
    """Successful single tenant role response."""
    success: Literal[True] = True
    message: str = "Éxito"
    role: TenantRoleResponse


class TenantRoleErrorResponse(BaseModel):
    """Error response for tenant role operations."""
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
