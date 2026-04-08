"""
Tenant Migration Utilities

Utilities for managing tenant database schemas and migrations.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from ..databases.tenant_db_factory import get_tenant_engine, tenant_metadata


async def run_tenant_migrations(tenant_id: int):
    """
    Run migrations on a tenant's database.
    Creates all tables registered in tenant_metadata.
    
    Ensures all models are imported so they register with metadata.
    """
    from .models_loader import import_tenant_models
    import_tenant_models()
    
    engine = get_tenant_engine(tenant_id)

    async with engine.begin() as conn:
        await conn.run_sync(tenant_metadata.create_all)

    print(f"✅ Ran migrations for tenant {tenant_id}")


async def seed_tenant_data(tenant_id: int, seed_data: dict | None = None):
    """
    Seed initial data for a tenant's database.

    Args:
        tenant_id: Tenant's ID
        seed_data: Optional dictionary of seed data
    """
    engine = get_tenant_engine(tenant_id)

    async with AsyncSession(engine) as session:
        # Add your seed data logic here
        await session.commit()

    print(f"✅ Seeded data for tenant {tenant_id}")


async def drop_all_tenant_tables(tenant_id: int):
    """
    Drop all tables in a tenant's database.
    USE WITH CAUTION!

    Args:
        tenant_id: Tenant's ID
    """
    engine = get_tenant_engine(tenant_id)

    async with engine.begin() as conn:
        await conn.run_sync(tenant_metadata.drop_all)

    print(f"🗑️  Dropped all tables for tenant {tenant_id}")


async def run_all_tenant_migrations():
    """
    Run migrations on all active tenant databases.
    Useful when you add new models/fields.
    """
    from sqlalchemy import select
    from pgsqlasync2fast_fastapi.connection import get_manager
    auth_engine = get_manager().get_engine("auth")
    from tenant2fast_fastapi.models.tenant_model import Tenant
    
    async with AsyncSession(auth_engine) as session:
        result = await session.execute(select(Tenant).where(Tenant.is_active == True))  # noqa: E712
        tenants = result.scalars().all()

        for tenant in tenants:
            try:
                await run_tenant_migrations(tenant.id)
            except Exception as e:
                print(f"❌ Failed to migrate tenant {tenant.id}: {e}")

        print(f"✅ Migrated {len(tenants)} tenant databases")


async def seed_all_tenants():
    """
    Run the RBAC seeder on all active tenant databases.
    Ensures roles and permissions are up to date across the entire platform.
    """
    from sqlalchemy import select
    from pgsqlasync2fast_fastapi.connection import get_manager
    auth_engine = get_manager().get_engine("auth")
    
    from tenant2fast_fastapi.models.tenant_model import Tenant
    from ..services.tenant_rbac_seeder import seed_tenant_rbac

    async with AsyncSession(auth_engine) as session:
        result = await session.execute(select(Tenant).where(Tenant.is_active == True))  # noqa: E712
        tenants = result.scalars().all()

        for tenant in tenants:
            try:
                await seed_tenant_rbac(tenant.id)
            except Exception as e:
                print(f"❌ Failed to seed tenant {tenant.id}: {e}")

        print(f"✅ Seeded {len(tenants)} tenant databases with default RBAC")
