"""
test_models.py – integration tests for Tenant and UserTenant models.

Requires a running PostgreSQL instance configured via .env.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from tenant2fast_fastapi.models.tenant_model import Tenant2
from tenant2fast_fastapi.models.user_tenant_model import UserTenant2


@pytest.mark.asyncio
async def test_create_tenant(session: AsyncSession):
    """Tenant can be persisted and retrieved from the database."""
    tenant = Tenant2(
        name="Test Corp",
        slug="test-corp",
        database_name="tenant_test_corp",
        is_active=True,
        contact_email="test@corp.com",
    )
    session.add(tenant)
    await session.commit()
    await session.refresh(tenant)

    assert tenant.id is not None
    assert tenant.slug == "test-corp"
    assert tenant.is_active is True


@pytest.mark.asyncio
async def test_tenant_slug_is_unique(session: AsyncSession):
    """Two tenants with the same slug must raise an integrity error."""
    from sqlalchemy.exc import IntegrityError

    t1 = Tenant2(name="Corp A", slug="unique-slug", database_name="tenant_corp_a", is_active=True)
    t2 = Tenant2(name="Corp B", slug="unique-slug", database_name="tenant_corp_b", is_active=True)

    session.add(t1)
    await session.commit()

    session.add(t2)
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_associate_user_to_tenant(session: AsyncSession, test_user, test_tenant):
    """A UserTenant row correctly links User and Tenant."""
    user_tenant = UserTenant2(user_id=test_user.id, tenant_id=test_tenant.id)
    session.add(user_tenant)
    await session.commit()
    await session.refresh(user_tenant)

    assert user_tenant.id is not None
    assert user_tenant.user_id == test_user.id
    assert user_tenant.tenant_id == test_tenant.id


@pytest.mark.asyncio
async def test_query_tenants_for_user(session: AsyncSession, test_user, test_tenant):
    """All tenants associated with a user can be selected."""
    user_tenant = UserTenant2(user_id=test_user.id, tenant_id=test_tenant.id)
    session.add(user_tenant)
    await session.commit()

    result = await session.execute(
        select(UserTenant2).where(UserTenant2.user_id == test_user.id)
    )
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].tenant_id == test_tenant.id


@pytest.mark.asyncio
async def test_inactive_tenant(session: AsyncSession):
    """A tenant can be created as inactive."""
    tenant = Tenant2(
        name="Old Corp",
        slug="old-corp",
        database_name="tenant_old_corp",
        is_active=False,
    )
    session.add(tenant)
    await session.commit()
    await session.refresh(tenant)

    assert tenant.is_active is False
