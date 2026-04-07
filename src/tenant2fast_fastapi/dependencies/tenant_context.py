"""
Tenant Context Management

This module provides context management for tenant resolution in FastAPI.
The tenant context is set by middleware and can be accessed via dependency injection.
"""

from contextvars import ContextVar

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from permissions2fast_fastapi.utils import cache_tenant_data, get_tenant_data
from oauth2fast_fastapi import get_auth_session
from oauth2fast_fastapi.models.user_model import User
from ..models import Tenant

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


async def get_current_tenant() -> Tenant:
    """
    FastAPI dependency to get current tenant.
    Raises 403 if no tenant in context.
    """
    tenant = get_tenant_context()

    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tenant context available. Authentication required.",
        )

    if not tenant.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant is inactive.",
        )

    return tenant


async def get_current_user() -> User:
    """
    FastAPI dependency to get current user.
    Raises 401 if no user in context.
    """
    user = get_user_context()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    return user


async def load_tenant_by_id(tenant_id: int) -> Tenant | None:
    """
    Load tenant from database or cache.

    Args:
        tenant_id: Tenant's ID

    Returns:
        Tenant object or None if not found
    """
    # Try cache first
    cached_data = await get_tenant_data(tenant_id)
    if cached_data:
        # Pydantic will handle the mapping from dict
        return Tenant(**cached_data)

    # Load from database
    session: AsyncSession = get_auth_session()
    async with session:
        result = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()

        if tenant:
            await cache_tenant_data(
                tenant_id,
                {
                    "id": tenant.id,
                    "name": tenant.name,
                    "slug": tenant.slug,
                    "database_name": tenant.database_name,
                    "is_active": tenant.is_active,
                    "contact_email": tenant.contact_email,
                    "max_users": tenant.max_users,
                    "created_at": tenant.created_at.isoformat(),
                    "updated_at": tenant.updated_at.isoformat(),
                },
            )

        return tenant

