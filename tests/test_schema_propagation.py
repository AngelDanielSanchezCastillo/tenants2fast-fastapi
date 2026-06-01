"""
test_schema_propagation.py – tests for mass migration and seeding across all tenants.
"""

import pytest
from sqlmodel import select
from tenant2fast_fastapi.models.tenant_model import Tenant
from tenant2fast_fastapi.models.role_model import Role
from tenant2fast_fastapi.utils.tenant_migrations import (
    run_all_tenant_migrations,
    seed_all_tenants,
)
from tenant2fast_fastapi.databases.tenant_db_factory import (
    create_tenant_database,
    get_tenant_session,
    dispose_tenant_engine,
    delete_tenant_database,
)

import uuid

@pytest.mark.asyncio
async def test_run_migrations_and_seed_all_tenants(session):
    """
    Verify that migrations and seeding can be propagated to multiple tenants.
    """
    # 1. Create two active tenants in Auth DB
    suffix = uuid.uuid4().hex[:6]
    tenant_a = Tenant(name="Tenant A", slug=f"tenant-a-{suffix}", database_name=f"db_a_{suffix}", is_active=True)
    tenant_b = Tenant(name="Tenant B", slug=f"tenant-b-{suffix}", database_name=f"db_b_{suffix}", is_active=True)
    tenant_c = Tenant(name="Tenant C", slug=f"tenant-c-{suffix}", database_name=f"db_c_{suffix}", is_active=False) # Inactive
    
    session.add(tenant_a)
    session.add(tenant_b)
    session.add(tenant_c)
    await session.commit()
    await session.refresh(tenant_a)
    await session.refresh(tenant_b)
    await session.refresh(tenant_c)

    try:
        # 2. Provision their databases manually (to simulate existing tenants)
        await create_tenant_database(tenant_a.id)
        await create_tenant_database(tenant_b.id)
        # We don't provision C to see if it's skipped or if it fails gracefully
        
        # 3. Run all migrations
        await run_all_tenant_migrations()
        
        # 4. Run all seeders
        await seed_all_tenants()
        
        # 5. Verify results in Tenant A
        session_a = await get_tenant_session(tenant_a.id)
        async with session_a:
            roles = await session_a.exec(select(Role))
            assert len(roles.all()) == 3
            
        # 6. Verify results in Tenant B
        session_b = await get_tenant_session(tenant_b.id)
        async with session_b:
            roles = await session_b.exec(select(Role))
            assert len(roles.all()) == 3
            
    finally:
        # Cleanup
        await delete_tenant_database(tenant_a.id)
        await delete_tenant_database(tenant_b.id)
        # Tenant C doesn't have a DB to delete
