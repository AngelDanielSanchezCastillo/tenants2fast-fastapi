"""
Tenant Service

Business logic for tenant operations including database provisioning.
"""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from ..databases.tenant_db_factory import (
    create_tenant_database,
    delete_tenant_database,
    initialize_tenant_schema,
)
from ..schemas.tenant_schema import TenantCreate, TenantUpdate
from ..utils import cache_tenant_data  # Imports from permissions2fast
from ..models.tenant_model import Tenant
from .tenant_rbac_seeder import seed_tenant_rbac
from pgsqlasync2fast_fastapi.connection import get_manager


async def create_tenant(tenant_data: TenantCreate) -> Tenant:
    """
    Create a new tenant with database provisioning.

    Steps:
    1. Validate slug is unique
    2. Create tenant record in auth database
    3. Create dedicated PostgreSQL database for tenant
    4. Initialize schema in tenant database
    5. Seed default RBAC data (Owner, Admin, Member)
    6. Cache tenant data
    """
    async with await get_manager().get_session("auth") as session:
        # Check if slug already exists
        result = await session.execute(
            select(Tenant).where(Tenant.slug == tenant_data.slug)
        )
        existing = result.scalar_one_or_none()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tenant with slug '{tenant_data.slug}' already exists",
            )

        # Create tenant record
        tenant = Tenant(
            name=tenant_data.name,
            slug=tenant_data.slug,
            database_name=f"tenant_{tenant_data.slug}",  # Placeholder to satisfy unique + not null
            contact_email=tenant_data.contact_email,
            max_users=tenant_data.max_users,
        )

        session.add(tenant)
        await session.commit()
        await session.refresh(tenant)

        try:
            # Create dedicated database for tenant
            db_name = await create_tenant_database(tenant.id)

            # Update tenant with database name
            tenant.database_name = db_name
            session.add(tenant)
            await session.commit()
            await session.refresh(tenant)

            # Initialize schema in tenant database
            await initialize_tenant_schema(tenant.id)

            # Seed default RBAC data
            await seed_tenant_rbac(tenant.id)

            # Cache tenant data
            await cache_tenant_data(
                tenant.id,
                {
                    "id": tenant.id,
                    "name": tenant.name,
                    "slug": tenant.slug,
                    "database_name": tenant.database_name,
                    "is_active": tenant.is_active,
                    "contact_email": tenant.contact_email,
                    "max_users": tenant.max_users,
                    "created_at": tenant.created_at.isoformat(),
                    "updated_at": tenant.updated_at.isoformat(),
                },
            )

            print(f"✅ Successfully created tenant: {tenant.name} (ID: {tenant.id})")
            return tenant

        except Exception as e:
            # Rollback tenant creation if database creation fails
            await session.delete(tenant)
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create tenant database: {str(e)}",
            )


async def get_tenant_by_id(tenant_id: int) -> Tenant | None:
    """Get tenant by ID."""
    async with await get_manager().get_session("auth") as session:
        result = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
        return result.scalar_one_or_none()


async def get_tenant_by_slug(slug: str) -> Tenant | None:
    """Get tenant by slug."""
    async with await get_manager().get_session("auth") as session:
        result = await session.execute(select(Tenant).where(Tenant.slug == slug))
        return result.scalar_one_or_none()


async def list_tenants(skip: int = 0, limit: int = 100) -> tuple[list[Tenant], int]:
    """List all tenants with pagination."""
    async with await get_manager().get_session("auth") as session:
        count_result = await session.execute(select(Tenant))
        total = len(count_result.scalars().all())

        result = await session.execute(
            select(Tenant).offset(skip).limit(limit).order_by(Tenant.created_at.desc())
        )
        tenants = result.scalars().all()

        return list(tenants), total


async def update_tenant(tenant_id: int, tenant_data: TenantUpdate) -> Tenant:
    """Update tenant metadata."""
    async with await get_manager().get_session("auth") as session:
        result = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()

        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant {tenant_id} not found",
            )

        update_data = tenant_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(tenant, field, value)

        session.add(tenant)
        await session.commit()
        await session.refresh(tenant)

        await cache_tenant_data(
            tenant.id,
            {
                "id": tenant.id,
                "name": tenant.name,
                "slug": tenant.slug,
                "database_name": tenant.database_name,
                "is_active": tenant.is_active,
                "contact_email": tenant.contact_email,
                "max_users": tenant.max_users,
                "created_at": tenant.created_at.isoformat(),
                "updated_at": tenant.updated_at.isoformat(),
            },
        )

        return tenant


async def deactivate_tenant(tenant_id: int) -> Tenant:
    """Deactivate a tenant (soft delete)."""
    return await update_tenant(tenant_id, TenantUpdate(is_active=False))


async def delete_tenant_permanently(tenant_id: int):
    """
    Permanently delete a tenant and their database.
    USE WITH EXTREME CAUTION!
    """
    async with await get_manager().get_session("auth") as session:
        result = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()

        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant {tenant_id} not found",
            )

        await delete_tenant_database(tenant_id)
        await session.delete(tenant)
        await session.commit()

        print(f"🗑️  Permanently deleted tenant: {tenant.name} (ID: {tenant.id})")
