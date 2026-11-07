"""
Tenant auth error contract (0.9.0).

A tenant route must distinguish authentication from authorization:

- missing / expired / invalid token → 401 with the matching ``error.type``
  and RFC 6750 challenge
- valid token but no tenant, or an inactive tenant → 403 (no challenge)
"""

from datetime import timedelta

from httpx import ASGITransport, AsyncClient
from oauth2fast_fastapi.utils.token_utils import create_access_token

from tenant2fast_fastapi.models.tenant_model import Tenant
from tests.app_fixture import create_test_app


async def _client():
    app = create_test_app()
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_missing_token_returns_401_token_missing():
    async with await _client() as client:
        response = await client.get("/test/tenant-required")

    assert response.status_code == 401
    assert response.json()["error"]["type"] == "TokenMissing"
    assert response.headers.get("www-authenticate") == "Bearer"


async def test_expired_token_returns_401_not_403(test_user):
    token = create_access_token(
        {"sub": test_user.email}, expires_delta=timedelta(seconds=-5)
    )

    async with await _client() as client:
        response = await client.get(
            "/test/tenant-required",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 401
    assert response.json()["error"]["type"] == "TokenExpired"
    assert response.headers.get("www-authenticate") == 'Bearer error="expired_token"'


async def test_malformed_token_returns_401_token_invalid(test_user):
    async with await _client() as client:
        response = await client.get(
            "/test/tenant-required",
            headers={"Authorization": "Bearer not-a-jwt"},
        )

    assert response.status_code == 401
    assert response.json()["error"]["type"] == "TokenInvalid"
    assert response.headers.get("www-authenticate") == 'Bearer error="invalid_token"'


async def test_valid_token_without_tenant_returns_403_tenant_required(test_user):
    token = create_access_token({"sub": test_user.email})

    async with await _client() as client:
        response = await client.get(
            "/test/tenant-required",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 403
    assert response.json()["error"]["type"] == "TenantRequired"
    assert response.headers.get("www-authenticate") is None


async def test_inactive_tenant_returns_403_tenant_inactive(
    test_user, test_tenant, user_tenant_link, session
):
    persisted = await session.get(Tenant, test_tenant.id)
    assert persisted is not None
    persisted.is_active = False
    session.add(persisted)
    await session.commit()

    token = create_access_token({"sub": test_user.email})

    async with await _client() as client:
        response = await client.get(
            "/test/tenant-required",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 403
    assert response.json()["error"]["type"] == "TenantInactive"


async def test_valid_token_with_tenant_returns_200(
    test_user, test_tenant, user_tenant_link
):
    token = create_access_token({"sub": test_user.email})

    async with await _client() as client:
        response = await client.get(
            "/test/tenant-required",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.json()["tenant_id"] == test_tenant.id
