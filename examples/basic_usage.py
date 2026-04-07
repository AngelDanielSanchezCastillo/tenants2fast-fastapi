"""
basic_usage.py – minimal example of tenants2fast-fastapi integration.

Demonstrates how to:
  1. Add TenantMiddleware to a FastAPI app
  2. Use get_current_tenant and get_current_user as dependencies
  3. Use require_permission to guard routes
"""

from fastapi import Depends, FastAPI

from tenant2fast_fastapi import (
    TenantMiddleware,
    get_current_tenant,
    get_current_user,
    require_permission,
)
from tenant2fast_fastapi.models.tenant_model import Tenant2Read

app = FastAPI(title="tenants2fast-fastapi Example")

# ── Register the tenant middleware ────────────────────────────────────────────
# Intercepts every request, decodes the JWT, and sets the tenant + user context
# before the request reaches the endpoint.
app.add_middleware(TenantMiddleware)


# ── Protected endpoints ───────────────────────────────────────────────────────

@app.get("/me/tenant", response_model=Tenant2Read)
async def get_my_tenant(tenant=Depends(get_current_tenant)):
    """Return the tenant for the authenticated user."""
    return tenant


@app.get("/me")
async def get_me(user=Depends(get_current_user)):
    """Return basic info about the authenticated user."""
    return {"id": user.id, "email": user.email}


@app.get(
    "/reports",
    dependencies=[Depends(require_permission("/reports", "GET"))],
)
async def get_reports(user=Depends(get_current_user)):
    """
    Permission-gated endpoint.
    The user must have an explicit permission or a role that grants GET /reports.
    """
    return {"message": f"Hello {user.email}, here are your reports."}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
