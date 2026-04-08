from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from oauth2fast_fastapi.models.user_model import User

from .tenant_context import get_current_tenant, get_current_user
from ..models import Tenant, TenantUser
from ..services.tenant_access_service import tenant_access_service
from ..services.tenant_role_service import tenant_role_service
from ..services.tenant_user_service import get_tenant_user_by_auth_id
from ..databases.tenant_db_factory import get_tenant_session
from ..utils.tenant_cache import (
    get_tenant_user_permissions_cache,
    set_tenant_user_permissions_cache,
)


def has_tenant_permission(
    permission_route: str | None = None,
    method: str | None = None,
):
    """
    Dependency to require permission for a route inside the current tenant.

    If both params are ``None``, the check is performed against the **current
    request path and method** — exactly like ``has_permission()`` in
    permissions2fast-fastapi.

    When ``permission_route`` is set, that explicit path is checked instead of
    the real request path.  This is useful when the stored route pattern
    differs from the URL (e.g. ``/users/{user_id}`` vs ``/users/42``).

    Implements an optional Redis caching strategy for performance.

    Usage::

        # Auto-detect route & method from the request
        @router.get("/reports")
        async def reports(_: bool = Depends(has_tenant_permission())):
            ...

        # Explicit route / method
        @router.delete("/reports/{report_id}")
        async def delete_report(
            _: bool = Depends(has_tenant_permission("/reports/{report_id}", "DELETE"))
        ):
            ...
    """
    async def _check(
        request: Request,
        tenant: Annotated[Tenant, Depends(get_current_tenant)],
        user: Annotated[User, Depends(get_current_user)],
    ) -> bool:
        # -- Resolve route/method to check ------------------------------------
        if permission_route is not None:
            route_to_check = permission_route
        else:
            # Use the FastAPI route template (e.g. /users/{user_id}) so it
            # matches the patterns stored in the DB — same approach as
            # has_permission() in permissions2fast-fastapi.
            fastapi_route = request.scope.get("route")
            route_to_check = fastapi_route.path if fastapi_route else request.url.path

        method_to_check = method or request.method

        # -- Try Redis cache first --------------------------------------------
        permissions = await get_tenant_user_permissions_cache(tenant.id, user.id)

        if permissions is None:
            # Cache miss — hit the tenant DB
            async with await get_tenant_session(tenant.id) as session:
                tenant_user = await get_tenant_user_by_auth_id(user.id, session)
                if not tenant_user:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="User is not registered in this tenant",
                    )

                permissions = await tenant_access_service.get_user_permissions(
                    tenant_user.id, session
                )

            # Populate cache for future requests
            await set_tenant_user_permissions_cache(tenant.id, user.id, permissions)

        # -- Evaluate ---------------------------------------------------------
        is_allowed = tenant_access_service.evaluate_route_access(
            permissions, route_to_check, method_to_check
        )

        if not is_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions to access this resource",
            )

        return True

    return _check


def has_tenant_role(role_name: str):
    """
    Dependency to require a specific tenant-level role.

    Checks that the authenticated user has been assigned the given role
    **inside the current tenant** (not at the global Auth level).

    Usage::

        @router.delete("/settings")
        async def delete_settings(
            user: TenantUser = Depends(has_tenant_role("Owner"))
        ):
            ...
    """
    async def _check(
        tenant: Annotated[Tenant, Depends(get_current_tenant)],
        user: Annotated[User, Depends(get_current_user)],
    ) -> TenantUser:
        async with await get_tenant_session(tenant.id) as session:
            tenant_user = await get_tenant_user_by_auth_id(user.id, session)
            if not tenant_user:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User is not registered in this tenant",
                )

            user_roles = await tenant_role_service.list_user_roles(
                tenant_user.id, session
            )

        has_required = any(r.name == role_name for r in user_roles)

        if not has_required:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required tenant role: {role_name}",
            )

        return tenant_user

    return _check


async def get_current_tenant_user(
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_user),
) -> TenantUser:
    """
    Dependency to get the current user's record inside the tenant.
    """
    async with await get_tenant_session(tenant.id) as session:
        tenant_user = await get_tenant_user_by_auth_id(user.id, session)
        if not tenant_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User record not found in tenant"
            )
        return tenant_user
