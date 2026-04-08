"""
test_middleware.py – integration tests for tenant resolution middleware.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from tests.app_fixture import create_test_app
from oauth2fast_fastapi.utils.token_utils import create_access_token


@pytest.mark.asyncio
async def test_middleware_resolves_tenant_from_db(test_user, test_tenant, user_tenant_link):
    """
    Verify that the middleware resolves the tenant from the Auth database
    when no cache is present.
    """
    app = create_test_app()
    # Mocking transport
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Create a valid JWT for the user
        token = create_access_token(data={"sub": test_user.email})
        headers = {"Authorization": f"Bearer {token}"}
        
        # Request context endpoint
        response = await ac.get("/test/context", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["tenant_id"] == test_tenant.id
        assert data["user_id"] == test_user.id


@pytest.mark.asyncio
async def test_middleware_supports_x_tenant_header(test_user, test_tenant, user_tenant_link):
    """
    Verify that the middleware respects X-Tenant-Id header if user has access.
    """
    app = create_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = create_access_token(data={"sub": test_user.email})
        
        # Test with the correct header
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Tenant-Id": str(test_tenant.id)
        }
        response = await ac.get("/test/context", headers=headers)
        assert response.status_code == 200
        assert response.json()["tenant_id"] == test_tenant.id

        # Test with an invalid header (user doesn't have access to tenant 999)
        headers["X-Tenant-Id"] = "999"
        response = await ac.get("/test/context", headers=headers)
        # Should fallback to the first available tenant in UserTenant (which is test_tenant)
        # because the logic says links[0] if requested not found
        assert response.status_code == 200
        assert response.json()["tenant_id"] == test_tenant.id


@pytest.mark.asyncio
async def test_middleware_caches_in_redis(test_user, test_tenant, user_tenant_link, redis_client):
    """
    Verify that tenant_id is cached in Redis after the first resolution.
    """
    from permissions2fast_fastapi.utils import get_user_tenant
    
    app = create_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = create_access_token(data={"sub": test_user.email})
        headers = {"Authorization": f"Bearer {token}"}
        
        # First request (DB hit)
        await ac.get("/test/context", headers=headers)
        
        # Verify cache
        cached_id = await get_user_tenant(test_user.id)
        assert cached_id == test_tenant.id


@pytest.mark.asyncio
async def test_middleware_handles_unauthenticated(test_tenant):
    """
    Verify that the middleware skips resolution for unauthenticated requests.
    Context should remain None.
    """
    app = create_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/test/context")
        assert response.status_code == 200
        data = response.json()
        assert data["tenant_id"] is None
        assert data["user_id"] is None
