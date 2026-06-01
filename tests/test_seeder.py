"""
test_seeder.py – tests for RBAC seeder and mass-update functionality.
"""

import pytest
from sqlmodel import select
from tenant2fast_fastapi.services.tenant_rbac_seeder import seed_tenant_rbac
from tenant2fast_fastapi.utils.tenant_migrations import seed_all_tenants
from tenant2fast_fastapi.models.role_model import Role
from tenant2fast_fastapi.models.permission_model import Permission
from tenant2fast_fastapi.databases.tenant_db_factory import get_tenant_session


@pytest.mark.asyncio
async def test_seed_tenant_rbac_creates_defaults(test_tenant):
    """Verify that the seeder creates the default roles and permissions."""
    # Already seeded in conftest.py test_tenant fixture, just verify
    session = await get_tenant_session(test_tenant.id)
    async with session:
        # Check Roles
        roles = await session.exec(select(Role))
        role_names = [r.name for r in roles.all()]
        assert "Owner" in role_names
        assert "Admin" in role_names
        assert "Member" in role_names

        # Check Permissions
        perms = await session.exec(select(Permission))
        perm_names = [p.name for p in perms.all()]
        assert "view_tenant_info" in perm_names


@pytest.mark.asyncio
async def test_seed_tenant_rbac_is_idempotent(test_tenant):
    """Verify that calling the seeder twice does not duplicate roles/permissions."""
    # First call happened in fixture
    await seed_tenant_rbac(test_tenant.id)
    
    session = await get_tenant_session(test_tenant.id)
    async with session:
        # Verify counts
        roles_count = await session.exec(select(Role))
        role_all = roles_count.all()
        # Should be exactly 3 (Owner, Admin, Member)
        assert len(role_all) == 3


@pytest.mark.asyncio
async def test_seed_all_tenants(test_tenant):
    """Verify mass update of all active tenants."""
    # We only have one tenant in fixture, but seed_all_tenants should work
    await seed_all_tenants()
    
    # Check if the tenant still has its data
    session = await get_tenant_session(test_tenant.id)
    async with session:
        roles = await session.exec(select(Role))
        assert len(roles.all()) == 3
