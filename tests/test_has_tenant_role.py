"""
test_has_tenant_role.py – tests for the has_tenant_role dependency.
"""

import pytest
from fastapi import Depends
from httpx import AsyncClient, ASGITransport
from tests.app_fixture import create_test_app
from oauth2fast_fastapi.utils.token_utils import create_access_token
from tenant2fast_fastapi import has_tenant_role
from tenant2fast_fastapi.models.user_model import User
from tenant2fast_fastapi.models.role_model import Role
from tenant2fast_fastapi.models.assignments_model import RoleUser


@pytest.mark.asyncio
async def test_role_granted(test_user, test_tenant, user_tenant_link, tenant_session):
    """Verify access is granted when user has the specific role."""
    # 1. Create User in tenant DB
    t_user = User(auth_user_id=test_user.id)
    tenant_session.add(t_user)
    await tenant_session.flush()

    # 2. Assign Role
    role = Role(name="TestOwner")
    tenant_session.add(role)
    await tenant_session.flush()
    
    assignment = RoleUser(user_id=t_user.id, role_id=role.id)
    tenant_session.add(assignment)
    await tenant_session.commit()

    app = create_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = create_access_token(data={"sub": test_user.email})
        headers = {"Authorization": f"Bearer {token}", "X-Tenant-Id": str(test_tenant.id)}
        
        # Test endpoint expects "TestOwner"
        @app.get("/test/role/testowner", dependencies=[Depends(has_tenant_role("TestOwner"))])
        async def test_role_testowner():
            return {"status": "ok"}

        response = await ac.get("/test/role/testowner", headers=headers)
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_role_denied_wrong_role(test_user, test_tenant, user_tenant_link, tenant_session):
    """Verify access is denied when user has a different role."""
    t_user = User(auth_user_id=test_user.id)
    tenant_session.add(t_user)
    
    role = Role(name="TestMember")
    tenant_session.add(role)
    await tenant_session.flush()
    
    assignment = RoleUser(user_id=t_user.id, role_id=role.id)
    tenant_session.add(assignment)
    await tenant_session.commit()

    app = create_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = create_access_token(data={"sub": test_user.email})
        headers = {"Authorization": f"Bearer {token}", "X-Tenant-Id": str(test_tenant.id)}
        
        # Guard is has_tenant_role("TestOwner")
        @app.get("/test/role/testowner", dependencies=[Depends(has_tenant_role("TestOwner"))])
        async def test_role_testowner():
            return {"status": "ok"}

        response = await ac.get("/test/role/testowner", headers=headers)
        assert response.status_code == 403
