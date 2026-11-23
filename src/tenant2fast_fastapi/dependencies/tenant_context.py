"""
Tenant Context Management

This module provides context management for tenant resolution in FastAPI.
The tenant context is set by middleware and can be accessed via dependency injection.
"""

from collections.abc import AsyncGenerator
from contextvars import ContextVar
from datetime import datetime
from uuid import UUID

from fastapi import Depends, Request
from oauth2fast_fastapi.models.user_model import User
from pgsqlasync2fast_fastapi.connection import get_manager
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from tools2fast_fastapi import AuthError, active_only

from ..databases.tenant_db_factory import get_tenant_session as get_factory_session
from ..models.tenant_model import Tenant
from ..utils.tenant_cache import (
    get_tenant_data_cache as get_tenant_data,
)
from ..utils.tenant_cache import (
    set_tenant_data_cache as cache_tenant_data,
)

# Context variable to store current tenant for the request
_tenant_context: ContextVar[Tenant | None] = ContextVar("tenant_context", default=None)

# Context variable to store current user for the request
_user_context: ContextVar[User | None] = ContextVar("user_context", default=None)


def set_tenant_context(tenant: Tenant | None):
    """Set the current tenant in context. Called by middleware."""
    _tenant_context.set(tenant)


def get_tenant_context() -> Tenant | None:
    """Get the current tenant from context."""
    return _tenant_context.get()


def set_user_context(user: User | None):
    """Set the current user in context. Called by middleware."""
    _user_context.set(user)


def get_user_context() -> User | None:
    """Get the current user from context."""
    return _user_context.get()


async def get_current_tenant(request: Request) -> Tenant:
    """
    FastAPI dependency to get the current tenant.

    Semantics:

    - Problems with the token itself (missing/expired/invalid) → 401.
    - A valid token whose user has no tenant, or a soft-deleted tenant → 403.

    The middleware records the token problem in ``request.state.auth_error``
    and a soft-deleted tenant in ``request.state.tenant_inactive``.
    """
    tenant = get_tenant_context()
    user = get_user_context()
    auth_error = getattr(request.state, "auth_error", None)

    if tenant is None:
        if auth_error == "expired":
            raise AuthError(
                error_code="TokenExpired",
                message="Token expirado",
                www_authenticate='Bearer error="expired_token"',
            )
        if auth_error in ("invalid", "malformed"):
            raise AuthError(
                error_code="TokenInvalid",
                message="Token inválido",
                www_authenticate='Bearer error="invalid_token"',
            )
        if getattr(request.state, "tenant_inactive", False):
            raise AuthError(
                error_code="TenantInactive",
                message="El tenant está inactivo",
                status_code=403,
            )
        if user is None:
            raise AuthError(
                error_code="TokenMissing",
                message="Autenticación requerida",
            )
        raise AuthError(
            error_code="TenantRequired",
            message="El usuario no tiene un tenant asociado",
            status_code=403,
        )

    # Soft-delete check: if tenant has deleted_at, it's inactive
    if tenant.deleted_at is not None:
        raise AuthError(
            error_code="TenantInactive",
            message="El tenant está inactivo",
            status_code=403,
        )

    return tenant


async def get_current_user(request: Request) -> User:
    """
    FastAPI dependency to get the current user.

    Raises 401 with ``TokenMissing`` / ``TokenExpired`` / ``TokenInvalid``
    depending on why the token could not be used.
    """
    user = get_user_context()

    if user is None:
        auth_error = getattr(request.state, "auth_error", None)
        if auth_error == "expired":
            raise AuthError(
                error_code="TokenExpired",
                message="Token expirado",
                www_authenticate='Bearer error="expired_token"',
            )
        if auth_error in ("invalid", "malformed"):
            raise AuthError(
                error_code="TokenInvalid",
                message="Token inválido",
                www_authenticate='Bearer error="invalid_token"',
            )
        raise AuthError(
            error_code="TokenMissing",
            message="Autenticación requerida",
        )

    return user


async def load_tenant_by_id(tenant_id: UUID) -> Tenant | None:
    """
    Load tenant from database or cache.
    """
    # Try cache first
    cached_data = await get_tenant_data(tenant_id)
    if cached_data:
        return Tenant(**cached_data)

    # Load from database manually using the manager
    try:
        manager = get_manager()
        auth_engine = manager.get_engine("auth")

        async with AsyncSession(auth_engine, expire_on_commit=False) as session:
            result = await session.exec(select(Tenant).where(Tenant.id == tenant_id))
            tenant = result.one_or_none()

            if tenant:
                # Prepare data for cache
                # Serialize datetimes to ISO strings for JSON cache
                data = tenant.model_dump()
                for key, val in data.items():
                    if isinstance(val, (datetime)):
                        data[key] = val.isoformat()
                    elif isinstance(val, UUID):
                        data[key] = str(val)

                await cache_tenant_data(tenant_id, data)

            return tenant
    except Exception as e:
        print(f"⚠️  Error loading tenant by ID: {e}")
        return None


async def get_tenant_db_session(
    tenant: Tenant = Depends(get_current_tenant),
) -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency to get an AsyncSession for the current tenant's database.
    """
    session = await get_factory_session(tenant.id)
    try:
        yield session
    finally:
        await session.close()
