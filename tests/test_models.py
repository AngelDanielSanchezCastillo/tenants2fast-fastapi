"""
test_models.py – integration tests for Tenant and TenantUser models.

Requires a running PostgreSQL instance configured via .env.
"""

import pytest
from uuid import UUID
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from tenant2fast_fastapi.models.tenant_model import Tenant
from tenant2fast_fastapi.models.user_tenant_model import TenantUser


@pytest.mark.asyncio
async def test_create_tenant(session: AsyncSession):
    """Tenant can be persisted and retrieved from the database."""
    tenant = Tenant(
        name="Test Corp",
        slug="test-corp",
        database_name="tenant_test_corp",
        contact_email="test@corp.com",
    )
    session.add(tenant)
    await session.commit()
    await session.refresh(tenant)

    assert tenant.id is not None
    assert isinstance(tenant.id, UUID)
    assert tenant.slug == "test-corp"
    assert tenant.deleted_at is None  # Active = not soft-deleted


@pytest.mark.asyncio
async def test_tenant_slug_is_unique(session: AsyncSession):
    """Two tenants with the same slug must raise an integrity error."""
    from sqlalchemy.exc import IntegrityError

    t1 = Tenant(name="Corp A", slug="unique-slug", database_name="tenant_corp_a")
    t2 = Tenant(name="Corp B", slug="unique-slug", database_name="tenant_corp_b")

    session.add(t1)
    await session.commit()

    session.add(t2)
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_associate_user_to_tenant(session: AsyncSession, test_user, test_tenant):
    """A TenantUser row correctly links User and Tenant."""
    user_tenant = TenantUser(user_id=test_user.id, tenant_id=test_tenant.id)
    session.add(user_tenant)
    await session.commit()
    await session.refresh(user_tenant)

    assert user_tenant.id is not None
    assert isinstance(user_tenant.id, UUID)
    assert isinstance(user_tenant.user_id, UUID)
    assert isinstance(user_tenant.tenant_id, UUID)
    assert user_tenant.user_id == test_user.id
    assert user_tenant.tenant_id == test_tenant.id


@pytest.mark.asyncio
async def test_query_tenants_for_user(session: AsyncSession, test_user, test_tenant):
    """All tenants associated with a user can be selected."""
    user_tenant = TenantUser(user_id=test_user.id, tenant_id=test_tenant.id)
    session.add(user_tenant)
    await session.commit()

    result = await session.exec(select(TenantUser).where(TenantUser.user_id == test_user.id)
    )
    rows = result.all()
    assert len(rows) == 1
    assert rows[0].tenant_id == test_tenant.id


@pytest.mark.asyncio
async def test_tenant_soft_delete(session: AsyncSession):
    """A tenant can be soft-deleted via SoftDeleteMixin."""
    tenant = Tenant(
        name="Old Corp",
        slug="old-corp",
        database_name="tenant_old_corp",
    )
    session.add(tenant)
    await session.commit()
    await session.refresh(tenant)

    assert tenant.deleted_at is None

    # Soft-delete
    from tools2fast_fastapi import soft_delete
    from datetime import datetime, timezone
    tenant.deleted_at = datetime.now(timezone.utc)
    session.add(tenant)
    await session.commit()
    await session.refresh(tenant)

    assert tenant.deleted_at is not None
