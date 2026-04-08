"""
app_fixture.py - real FastAPI test application for tenant2fast-fastapi.

Registers Middleware and RBAC routers to test end-to-end flows.
"""

from fastapi import FastAPI, Depends
from tenant2fast_fastapi import (
    TenantMiddleware,
    has_tenant_permission,
    has_tenant_role,
    get_current_tenant_user,
    get_current_tenant,
    get_current_user,
)
from tenant2fast_fastapi.routers import get_tenant_routers


def create_test_app() -> FastAPI:
    """Create a FastAPI app with tenant2fast-fastapi integration."""
    app = FastAPI(title="Tenant2Fast Test App")

    # 1. Register Middleware
    app.add_middleware(TenantMiddleware)

    # 2. Register RBAC Routers (Users, Roles, Permissions)
    app.include_router(get_tenant_routers())

    # 3. Dedicated test endpoints for dependencies
    
    from tenant2fast_fastapi import get_tenant_context, get_user_context
    
    @app.get("/test/context")
    async def test_context(
        tenant=Depends(get_tenant_context),
        user=Depends(get_user_context)
    ):
        """Return the current tenant and user status."""
        return {
            "tenant_id": tenant.id if tenant else None,
            "user_id": user.id if user else None,
            "tenant_name": tenant.name if tenant else None,
        }

    @app.get("/test/permission", dependencies=[Depends(has_tenant_permission())])
    async def test_permission():
        """Route protected by auto-detected permission (GET /test/permission)."""
        return {"status": "ok"}

    @app.delete("/test/roles/{role_id}", dependencies=[Depends(has_tenant_permission("/test/roles/{role_id}", "DELETE"))])
    async def test_explicit_permission(role_id: int):
        """Route protected by explicit permission pattern."""
        return {"status": "ok", "role_id": role_id}

    @app.get("/test/role/owner", dependencies=[Depends(has_tenant_role("Owner"))])
    async def test_role_owner(user=Depends(get_current_tenant_user)):
        """Route protected by specific role."""
        return {"status": "ok", "tenant_user_id": user.id}

    @app.get("/test/me")
    async def test_me(user=Depends(get_current_tenant_user)):
        """Route returning the current tenant user data."""
        return {
            "id": user.id,
            "auth_user_id": user.auth_user_id,
            "position": user.position,
        }

    return app
