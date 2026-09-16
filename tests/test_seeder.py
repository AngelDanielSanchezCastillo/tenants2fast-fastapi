"""
test_seeder.py – tests for RBAC seeder and mass-update functionality.
"""

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from tenant2fast_fastapi.services.tenant_rbac_seeder import seed_tenant_rbac, _seed_table_idempotent
from tenant2fast_fastapi.utils.tenant_migrations import seed_all_tenants
from tenant2fast_fastapi.models.role_model import Role
from tenant2fast_fastapi.models.permission_model import Permission
from tenant2fast_fastapi.databases.tenant_db_factory import get_tenant_session


async def _tenant_engine():
    """In-memory SQLite engine with the tenant RBAC schema (no Postgres needed)."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlmodel.ext.asyncio.session import AsyncSession
    from tenant2fast_fastapi.models.bases import tenant_metadata
    from tenant2fast_fastapi.utils.models_loader import import_tenant_models

    import_tenant_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(tenant_metadata.create_all)
    return engine


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


# ============================================================================
# W2: permission_category_id (nullable) — SQLite-only, no Postgres required
# ============================================================================


@pytest.mark.asyncio
async def test_seed_permissions_maps_category_id_to_permission_category_id():
    """Seed rows declaring category_id populate permission_category_id (D2)."""
    engine = await _tenant_engine()
    async with AsyncSession(engine) as session:
        inserted, skipped = await _seed_table_idempotent(
            session,
            "permissions",
            [{"id": 1, "name": "view_tenant_info", "category_id": 1}],
            Permission,
        )
        assert inserted == 1
        perms = (await session.exec(select(Permission))).all()
        assert [(p.id, p.name, p.permission_category_id) for p in perms] == [
            (1, "view_tenant_info", 1)
        ]
    await engine.dispose()


@pytest.mark.asyncio
async def test_seed_permissions_reseed_updates_category_without_duplicating():
    """Reseed updates permission_category_id when it differs; no duplicate rows."""
    engine = await _tenant_engine()
    rows_v1 = [{"id": 1, "name": "view_tenant_info", "category_id": 1}]

    async with AsyncSession(engine) as session:
        await _seed_table_idempotent(session, "permissions", rows_v1, Permission)

    # Reseed with a DIFFERENT category -> UPDATE, no new row.
    async with AsyncSession(engine) as session:
        inserted, skipped = await _seed_table_idempotent(
            session,
            "permissions",
            [{"id": 1, "name": "view_tenant_info", "category_id": 2}],
            Permission,
        )
        assert inserted == 0
        perms = (await session.exec(select(Permission))).all()
        assert [(p.id, p.permission_category_id) for p in perms] == [(1, 2)]

    # Second identical reseed -> state unchanged (idempotent).
    async with AsyncSession(engine) as session:
        await _seed_table_idempotent(
            session,
            "permissions",
            [{"id": 1, "name": "view_tenant_info", "category_id": 2}],
            Permission,
        )
        perms = (await session.exec(select(Permission))).all()
        assert len(perms) == 1
        assert perms[0].permission_category_id == 2
    await engine.dispose()


@pytest.mark.asyncio
async def test_seed_permissions_without_category_keeps_null():
    """Seed rows without category_id keep permission_category_id NULL (spec null-safe)."""
    engine = await _tenant_engine()
    async with AsyncSession(engine) as session:
        inserted, skipped = await _seed_table_idempotent(
            session,
            "permissions",
            [{"id": 3, "name": "no_category_permission"}],
            Permission,
        )
        assert inserted == 1
        perms = (await session.exec(select(Permission))).all()
        assert [(p.id, p.permission_category_id) for p in perms] == [(3, None)]
    await engine.dispose()
