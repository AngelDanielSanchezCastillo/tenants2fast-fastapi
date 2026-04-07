"""
Tenant Middleware

This middleware intercepts all HTTP requests to:
1. Extract the user from JWT token
2. Load the user's tenant from database/cache
3. Load user permissions from cache
4. Set tenant and user context for the request lifecycle

This provides automatic tenant resolution without repetitive code in endpoints.
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..dependencies.tenant_context import (
    load_tenant_by_id,
    set_tenant_context,
    set_user_context,
)
from permissions2fast_fastapi.utils import (
    cache_user_permissions,
    cache_user_tenant,
    get_user_permissions,
    get_user_tenant,
)


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Middleware to resolve tenant context from authenticated user.

    Request Flow:
    1. Request arrives with JWT token
    2. Middleware decodes JWT to get user_id
    3. Checks Redis cache for user's tenant_id
    4. If not cached, loads from auth database
    5. Loads tenant data (from cache or database)
    6. Loads user permissions (from cache or database)
    7. Sets context variables for the request
    8. Request proceeds to endpoint with tenant context available
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        """
        Process each request to set tenant context.

        Args:
            request: FastAPI request object
            call_next: Next middleware/endpoint in chain

        Returns:
            Response from endpoint
        """
        # Reset context for this request
        set_tenant_context(None)
        set_user_context(None)

        # Skip tenant resolution for public endpoints
        if self._is_public_endpoint(request.url.path):
            return await call_next(request)

        # Try to extract user from request
        user = await self._get_user_from_request(request)

        if user:
            # Load tenant for this user
            tenant_id = await self._get_user_tenant_id(user.id)

            if tenant_id:
                # Load tenant data
                tenant = await load_tenant_by_id(tenant_id)

                if tenant:
                    # Set context for this request
                    set_tenant_context(tenant)
                    set_user_context(user)

                    # Ensure permissions are cached
                    await self._ensure_permissions_cached(user.id)

                    # Log tenant access (optional)
                    print(f"🏢 Request from user {user.id} (tenant: {tenant.name})")

        # Continue to endpoint
        response = await call_next(request)
        return response

    def _is_public_endpoint(self, path: str) -> bool:
        """
        Check if endpoint is public (doesn't require tenant context).

        Args:
            path: Request path

        Returns:
            True if public endpoint
        """
        public_paths = [
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health",
            "/auth/login",
            "/auth/register",
            "/auth/verify-email",
        ]

        return any(path.startswith(public_path) for public_path in public_paths)

    async def _get_user_from_request(self, request: Request):
        """
        Extract user from JWT token in request.

        Args:
            request: FastAPI request

        Returns:
            User object or None
        """
        # Get authorization header
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            return None

        token = auth_header.split(" ")[1]

        try:
            # Decode JWT and get user
            from sqlalchemy.ext.asyncio import AsyncSession
            from sqlmodel import select

            from oauth2fast_fastapi import engine as auth_engine
            from oauth2fast_fastapi.models.user_model import User
            from oauth2fast_fastapi.utils.token_utils import verify_token

            payload = verify_token(token)
            if not payload:
                return None

            email = payload.get("sub")
            if not email:
                return None

            # Load user from database
            async with AsyncSession(auth_engine) as session:
                result = await session.execute(select(User).where(User.email == email))
                user = result.scalar_one_or_none()
                return user

        except Exception as e:
            print(f"⚠️  Error extracting user from token: {e}")
            return None

    async def _get_user_tenant_id(self, user_id: int) -> int | None:
        """
        Get user's tenant ID from cache or database.

        Args:
            user_id: User's ID

        Returns:
            Tenant ID or None
        """
        # Check cache first
        tenant_id = await get_user_tenant(user_id)

        if tenant_id:
            return tenant_id

        # Load from database
        from sqlalchemy.ext.asyncio import AsyncSession
        from sqlmodel import select

        from oauth2fast_fastapi import engine as auth_engine
        from oauth2fast_fastapi.models.user_model import User

        async with AsyncSession(auth_engine) as session:
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

            if user and user.tenant_id:
                # Cache for future requests
                await cache_user_tenant(user_id, user.tenant_id)
                return user.tenant_id

        return None

    async def _ensure_permissions_cached(self, user_id: int):
        """
        Ensure user permissions are in cache.
        If not, load from database and cache them.

        Args:
            user_id: User's ID
        """
        # Check if already cached
        cached_perms = await get_user_permissions(user_id)

        if cached_perms is not None:
            return  # Already cached

        # Load from database
        from sqlalchemy.ext.asyncio import AsyncSession
        from sqlmodel import select

        from permissions2fast_fastapi.models import UserPermission
        from oauth2fast_fastapi import engine as auth_engine

        async with AsyncSession(auth_engine) as session:
            result = await session.execute(
                select(UserPermission).where(UserPermission.user_id == user_id)
            )
            permissions = result.scalars().all()

            # Convert to dict for caching
            perm_dicts = [
                {
                    "route_path": p.route_path,
                    "method": p.method,
                    "is_allowed": p.is_allowed,
                    "expires_at": p.expires_at.isoformat() if p.expires_at else None,
                }
                for p in permissions
            ]

            # Cache permissions
            await cache_user_permissions(user_id, perm_dicts)
