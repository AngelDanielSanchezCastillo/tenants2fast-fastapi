"""
test_has_tenant_permission.py – tests for the has_tenant_permission dependency.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from tests.app_fixture import create_test_app
from oauth2fast_fastapi.utils.token_utils import create_access_token
from tenant2fast_fastapi.models.user_model import User
from tenant2fast_fastapi.models.role_model import Role
from tenant2fast_fastapi.models.permission_model import Permission
from tenant2fast_fastapi.models.route_model import Route
from tenant2fast_fastapi.models.assignments_model import (
    RoleUser,
    PermissionRole,
    PermissionRoute,
    PermissionUser
)


@pytest.fixture
async def setup_rbac(tenant_session, test_user):
    """Setup a basic RBAC structure in the tenant DB."""
    # 1. Create User in tenant DB
    t_user = User(auth_user_id=test_user.id, position="Manager")
    tenant_session.add(t_user)
    await tenant_session.commit()
    await tenant_session.refresh(t_user)

    # 2. Create Permission & Route
    route = Route(path="/test/permission", method="GET")
    tenant_session.add(route)
    await tenant_session.flush()
    
    perm = Permission(name="TestPermission")
    tenant_session.add(perm)
    await tenant_session.flush()
    
    link_route = PermissionRoute(permission_id=perm.id, route_id=route.id)
    tenant_session.add(link_route)
    
    # 3. Create Role and assign permission
    role = Role(name="TestPermissionRole")
    tenant_session.add(role)
    await tenant_session.flush()
    
    link_role_perm = PermissionRole(role_id=role.id, permission_id=perm.id)
    tenant_session.add(link_role_perm)
    
    await tenant_session.commit()
    return {"user": t_user, "role": role, "perm": perm, "route": route}


@pytest.mark.asyncio
async def test_permission_granted_via_role(test_user, test_tenant, user_tenant_link, setup_rbac, tenant_session):
    """Verify access is granted when user has a role with the permission."""
    # Assign role to user
    assignment = RoleUser(user_id=setup_rbac["user"].id, role_id=setup_rbac["role"].id)
    tenant_session.add(assignment)
    await tenant_session.commit()

    app = create_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = create_access_token(data={"sub": test_user.email})
        headers = {"Authorization": f"Bearer {token}", "X-Tenant-Id": str(test_tenant.id)}
        
        response = await ac.get("/test/permission", headers=headers)
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_permission_denied_no_role(test_user, test_tenant, user_tenant_link, setup_rbac):
    """Verify access is denied when user has no roles."""
    app = create_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = create_access_token(data={"sub": test_user.email})
        headers = {"Authorization": f"Bearer {token}", "X-Tenant-Id": str(test_tenant.id)}
        
        response = await ac.get("/test/permission", headers=headers)
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_permission_pattern_matching(test_user, test_tenant, user_tenant_link, tenant_session, setup_rbac):
    """Verify route pattern matching (e.g. /test/roles/{role_id})."""
    # 1. Create a pattern route
    route = Route(path="/test/roles/{role_id}", method="DELETE")
    tenant_session.add(route)
    await tenant_session.flush()
    
    # 2. Link to existing permission
    link = PermissionRoute(permission_id=setup_rbac["perm"].id, route_id=route.id)
    tenant_session.add(link)
    
    # 3. Assign role to user
    assignment = RoleUser(user_id=setup_rbac["user"].id, role_id=setup_rbac["role"].id)
    tenant_session.add(assignment)
    await tenant_session.commit()

    app = create_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = create_access_token(data={"sub": test_user.email})
        headers = {"Authorization": f"Bearer {token}", "X-Tenant-Id": str(test_tenant.id)}
        
        # Test with an actual ID (should match pattern)
        response = await ac.delete("/test/roles/123", headers=headers)
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_direct_permission_override(test_user, test_tenant, user_tenant_link, tenant_session, setup_rbac):
    """Verify that a direct PermissionUser override works (Allow or Deny)."""
    # 1. User has the role (which allows the route)
    assignment = RoleUser(user_id=setup_rbac["user"].id, role_id=setup_rbac["role"].id)
    tenant_session.add(assignment)
    
    # 2. BUT we add a direct DENY override for the same permission
    override = PermissionUser(
        user_id=setup_rbac["user"].id, 
        permission_id=setup_rbac["perm"].id,
        is_allowed=False
    )
    tenant_session.add(override)
    await tenant_session.commit()

    app = create_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = create_access_token(data={"sub": test_user.email})
        headers = {"Authorization": f"Bearer {token}", "X-Tenant-Id": str(test_tenant.id)}
        
        # Should be DENIED because direct override takes precedence (if implemented that way)
        # Based on TenantAccessService.evaluate_route_access: 
        # it checks all resolved_permissions. If an is_allowed=False perm matches, it returns False.
        response = await ac.get("/test/permission", headers=headers)
        assert response.status_code == 403
