"""
test_tenant_provisioning.py – tests for tenant database creation and management.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine
from tenant2fast_fastapi.databases.tenant_db_factory import (
    create_tenant_database,
    get_tenant_engine,
    initialize_tenant_schema,
    dispose_tenant_engine,
    delete_tenant_database,
    _tenant_db_name,
)


@pytest.mark.asyncio
async def test_create_get_and_delete_tenant_db(event_loop):
    """
    Full lifecycle test: create, get engine, initialize, dispose, and delete.
    Note: we use a new random tenant ID to avoid conflicts.
    """
    tenant_id = 9999
    db_name = _tenant_db_name(tenant_id)
    
    try:
        # 1. Create DB
        created_name = await create_tenant_database(tenant_id)
        assert created_name == db_name

        # 2. Get Engine
        engine = get_tenant_engine(tenant_id)
        assert isinstance(engine, AsyncEngine)
        
        # 3. Get Engine again (should be cached)
        engine_2 = get_tenant_engine(tenant_id)
        assert engine is engine_2

        # 4. Initialize Schema
        # We don't assert tables here (Suite 3 does that), just that it doesn't crash
        await initialize_tenant_schema(tenant_id)

        # 5. Dispose Engine
        await dispose_tenant_engine(tenant_id)

    finally:
        # 6. Delete DB (cleanup)
        await delete_tenant_database(tenant_id)


@pytest.mark.asyncio
async def test_initialize_schema_is_idempotent():
    """Calling initialize_tenant_schema twice should not raise errors."""
    tenant_id = 8888
    try:
        await create_tenant_database(tenant_id)
        
        # First call
        await initialize_tenant_schema(tenant_id)
        
        # Second call
        await initialize_tenant_schema(tenant_id)
        
    finally:
        await delete_tenant_database(tenant_id)
