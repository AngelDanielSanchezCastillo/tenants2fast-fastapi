"""
Tenant Migration Utilities

Utilities for managing tenant database schemas and migrations.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel, select

from ..databases.tenant_db_factory import get_tenant_engine


async def run_tenant_migrations(tenant_id: int):
    """
    Run migrations on a tenant's database.
    Creates all tables registered in SQLModel.metadata.

    Args:
        tenant_id: Tenant's ID
    """
    engine = get_tenant_engine(tenant_id)

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

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
        await conn.run_sync(SQLModel.metadata.drop_all)

    print(f"🗑️  Dropped all tables for tenant {tenant_id}")


async def migrate_all_tenants():
    """
    Run migrations on all active tenant databases.
    Useful when you add new models/fields.
    """
    from oauth2fast_fastapi import get_auth_session
    from tenant2fast_fastapi.models import Tenant

    session: AsyncSession = get_auth_session()
    async with session:
        result = await session.execute(select(Tenant).where(Tenant.is_active == True))  # noqa: E712
        tenants = result.scalars().all()

    for tenant in tenants:
        try:
            await run_tenant_migrations(tenant.id)
        except Exception as e:
            print(f"❌ Failed to migrate tenant {tenant.id}: {e}")

    print(f"✅ Migrated {len(tenants)} tenant databases")
