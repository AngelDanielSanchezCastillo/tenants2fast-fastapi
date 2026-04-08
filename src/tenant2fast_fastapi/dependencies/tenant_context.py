"""
Tenant Context Management

This module provides context management for tenant resolution in FastAPI.
The tenant context is set by middleware and can be accessed via dependency injection.
"""

from contextvars import ContextVar
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from collections.abc import AsyncGenerator
from fastapi import Depends, HTTPException, status

from ..utils.tenant_cache import (
    get_tenant_data_cache as get_tenant_data,
    set_tenant_data_cache as cache_tenant_data,
)
from pgsqlasync2fast_fastapi.connection import get_manager
from oauth2fast_fastapi.models.user_model import User
from ..models.tenant_model import Tenant
from ..databases.tenant_db_factory import get_tenant_session as get_factory_session

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
            result = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
            tenant = result.scalar_one_or_none()

            if tenant:
                # Prepare data for cache
                # Serialize datetimes to ISO strings for JSON cache
                data = tenant.model_dump()
                for key, val in data.items():
                    if isinstance(val, (datetime)):
                        data[key] = val.isoformat()
                        
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

