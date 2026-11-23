"""
Tenant Resolution Middleware

This middleware extracts the tenant from the request (headers or user context)
and sets the tenant-specific database connection for the duration of the request.
"""

from uuid import UUID

from fastapi import Request, Response
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..databases.tenant_db_factory import register_tenant_engine
from ..dependencies.tenant_context import (
    load_tenant_by_id,
    set_tenant_context,
    set_user_context,
)
from ..utils.tenant_cache import (
    get_user_tenant_cache,
    set_user_tenant_cache,
)


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Middleware to resolve tenant for each request.
    """

    def __init__(
        self,
        app: ASGIApp,
        header_name: str = "X-Tenant-Id",
    ):
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(self, request: Request, call_next) -> Response:
        set_tenant_context(None)
        set_user_context(None)
        # Why authentication failed (None when no token / valid token). Read by
        # the context dependencies to choose 401 vs 403.
        request.state.auth_error = None
        request.state.tenant_inactive = False

        user, auth_error = await self._get_user_from_request(request)
        request.state.auth_error = auth_error

        if user:
            set_user_context(user)

            requested_tenant_id = None
            header_value = request.headers.get(self.header_name)
            if header_value:
                # Try to parse as UUID first, then fall back to int (legacy)
                try:
                    requested_tenant_id = UUID(header_value)
                except ValueError:
                    if header_value.isdigit():
                        requested_tenant_id = int(header_value)

            tenant_id = await self._get_user_tenant_id(user.id, requested_tenant_id)

            if tenant_id:
                tenant = await load_tenant_by_id(tenant_id)
                # Soft-delete check: tenant.deleted_at is None means active
                if tenant and tenant.deleted_at is None:
                    set_tenant_context(tenant)
                    await register_tenant_engine(tenant.id, tenant.database_name)

                    request.state.tenant_id = str(tenant.id)
                    request.state.tenant_slug = tenant.slug
                elif tenant and tenant.deleted_at is not None:
                    request.state.tenant_inactive = True

        response = await call_next(request)
        return response

    async def _get_user_from_request(self, request: Request):
        """Resolve the user, returning ``(user, auth_error_reason)``.

        ``auth_error_reason`` is ``None`` when no Authorization header was sent
        or when the token is valid. It carries ``"expired"``, ``"invalid"`` or
        ``"malformed"`` otherwise, so dependencies can return 401 instead of a
        misleading 403.
        """
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return None, None

        if not auth_header.startswith("Bearer "):
            return None, "malformed"

        token = auth_header.split(" ", 1)[1].strip()
        if not token:
            return None, "malformed"

        try:
            from oauth2fast_fastapi.models.user_model import User
            from oauth2fast_fastapi.utils.token_utils import verify_token_detailed
            from pgsqlasync2fast_fastapi.connection import get_manager

            payload, reason = verify_token_detailed(token)
            if reason is not None:
                return None, reason

            email = payload.get("sub") if payload else None
            if not email:
                return None, "invalid"

            manager = get_manager()
            auth_engine = manager.get_engine("auth")

            async with AsyncSession(auth_engine, expire_on_commit=False) as session:
                result = await session.exec(select(User).where(User.email == email))
                user = result.one_or_none()
                if user is None:
                    return None, "invalid"
                return user, None

        except Exception:
            return None, "invalid"

    async def _get_user_tenant_id(
        self, user_id: UUID, requested_tenant_id: UUID | int | None = None
    ) -> UUID | None:
        cached_id = await get_user_tenant_cache(user_id)
        if cached_id and (not requested_tenant_id or str(cached_id) == str(requested_tenant_id)):
            return cached_id if isinstance(cached_id, UUID) else UUID(str(cached_id))

        from pgsqlasync2fast_fastapi.connection import get_manager

        auth_engine = get_manager().get_engine("auth")

        async with AsyncSession(auth_engine, expire_on_commit=False) as session:
            from tenant2fast_fastapi.models.user_tenant_model import TenantUser

            result = await session.exec(
                select(TenantUser).where(TenantUser.user_id == user_id)
            )
            links = result.all()

            if not links:
                return None

            target_link = None
            if requested_tenant_id:
                target_link = next(
                    (l for l in links if str(l.tenant_id) == str(requested_tenant_id)), None
                )

            if not target_link:
                target_link = links[0]

            if target_link:
                await set_user_tenant_cache(user_id, target_link.tenant_id)
                return target_link.tenant_id

        return None
