"""
test_get_current_tenant_user.py – tests for the get_current_tenant_user dependency.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from tests.app_fixture import create_test_app
from oauth2fast_fastapi.utils.token_utils import create_access_token
from tenant2fast_fastapi.models.tenant_user_model import TenantUser


@pytest.mark.asyncio
async def test_get_current_tenant_user_returns_record(test_user, test_tenant, user_tenant_link, tenant_session):
    """Verify that get_current_tenant_user returns the correct tenant-internal user."""
    # 1. Create Tenant User
    t_user = TenantUser(auth_user_id=test_user.id, position="Developer")
    tenant_session.add(t_user)
    await tenant_session.commit()
    await tenant_session.refresh(t_user)

    app = create_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = create_access_token(data={"sub": test_user.email})
        headers = {"Authorization": f"Bearer {token}", "X-Tenant-Id": str(test_tenant.id)}
        
        # Test /test/me which returns the user data
        response = await ac.get("/test/me", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == t_user.id
        assert data["auth_user_id"] == test_user.id
        assert data["position"] == "Developer"


@pytest.mark.asyncio
async def test_get_current_tenant_user_raises_404_if_missing(test_user, test_tenant, user_tenant_link):
    """Verify that get_current_tenant_user raises 404 if the user is not in the tenant DB."""
    # We do NOT create the TenantUser here
    app = create_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = create_access_token(data={"sub": test_user.email})
        headers = {"Authorization": f"Bearer {token}", "X-Tenant-Id": str(test_tenant.id)}
        
        response = await ac.get("/test/me", headers=headers)
        assert response.status_code == 404
        assert response.json()["detail"] == "User record not found in tenant"
