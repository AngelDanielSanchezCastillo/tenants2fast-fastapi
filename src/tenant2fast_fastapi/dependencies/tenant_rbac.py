from fastapi import Depends, HTTPException, status
from oauth2fast_fastapi.models.user_model import User

from .tenant_context import get_current_tenant, get_current_user
from ..models import Tenant, TenantUser
from ..services.tenant_access_service import tenant_access_service
from ..services.tenant_user_service import get_tenant_user_by_auth_id
from ..databases.tenant_db_factory import get_tenant_session
from ..utils.tenant_cache import (
    get_tenant_user_permissions_cache,
    set_tenant_user_permissions_cache
)


def require_tenant_permission(route_path: str, method: str = "*"):
    """
    Dependency to protect routes with the tenant's internal RBAC.
    Implements an optional Redis caching strategy.
    """
    async def check_permissions(
        tenant: Tenant = Depends(get_current_tenant),
        user: User = Depends(get_current_user),
    ) -> bool:
        # 1. Try to resolve from Redis cache first
        permissions = await get_tenant_user_permissions_cache(tenant.id, user.id)
        
        if permissions is not None:
            # Cache hit: directly evaluate against the requested route
            has_access = tenant_access_service.evaluate_route_access(
                permissions, route_path, method
            )
        else:
            # 2. Cache miss: query the tenant database
            async with await get_tenant_session(tenant.id) as session:
                # Need to find the internal TenantUser ID first for get_user_permissions
                tenant_user = await get_tenant_user_by_auth_id(user.id, session)
                if not tenant_user:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="User is not registered in this tenant"
                    )
                
                # Resolve all permissions for this user
                permissions = await tenant_access_service.get_user_permissions(
                    tenant_user.id, session
                )
                
                # 3. Store in Redis for future requests
                await set_tenant_user_permissions_cache(tenant.id, user.id, permissions)
                
                # 4. Evaluate access
                has_access = tenant_access_service.evaluate_route_access(
                    permissions, route_path, method
                )

        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You don't have permission for this action in {tenant.name}"
            )
            
        return True

    return check_permissions


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
