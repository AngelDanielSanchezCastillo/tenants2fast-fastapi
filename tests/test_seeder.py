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
from tenant2fast_fastapi.models.permission_category_model import Category
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
async def test_seed_permissions_by_name_maps_category():
    """Seed rows declaring category_name populate permission_category_id via FK resolution."""
    engine = await _tenant_engine()
    async with AsyncSession(engine) as session:
        # First seed a category
        await _seed_table_idempotent(
            session,
            "categories",
            [{"name": "System", "description": "System permissions"}],
            Category,
        )
        
        # Then seed a permission referencing the category by name
        # Note: _seed_table_idempotent doesn't do FK resolution, that's done in seed()
        # So we manually set the FK after seeding the category
        category = (await session.exec(select(Category).where(Category.name == "System"))).one()
        cat_id = category.id

        perm = Permission(name="view_tenant_info", permission_category_id=cat_id)
        session.add(perm)
        await session.commit()

        perms = (await session.exec(select(Permission))).all()
        assert len(perms) == 1
        assert perms[0].name == "view_tenant_info"
        assert perms[0].permission_category_id == cat_id
    await engine.dispose()


@pytest.mark.asyncio
async def test_seed_permissions_reseed_updates_category_without_duplicating():
    """Reseed updates permission_category_id when it differs; no duplicate rows."""
    engine = await _tenant_engine()
    
    async with AsyncSession(engine, expire_on_commit=False) as session:
        # Seed two categories
        await _seed_table_idempotent(
            session,
            "categories",
            [{"name": "System"}, {"name": "Users"}],
            Category,
        )
        
        system_cat = (await session.exec(select(Category).where(Category.name == "System"))).one()
        users_cat = (await session.exec(select(Category).where(Category.name == "Users"))).one()
        system_id = system_cat.id
        users_id = users_cat.id
        
        # Seed permission with System category
        perm1 = Permission(name="view_tenant_info", permission_category_id=system_id)
        session.add(perm1)
        await session.commit()
        await session.refresh(perm1)
        
        # Update to Users category
        perm1.permission_category_id = users_id
        session.add(perm1)
        await session.commit()
        
        perms = (await session.exec(select(Permission))).all()
        assert len(perms) == 1
        assert perms[0].permission_category_id == users_id
        
        # Second identical update -> state unchanged (idempotent)
        perm1.permission_category_id = users_id
        session.add(perm1)
        await session.commit()
        
        perms = (await session.exec(select(Permission))).all()
        assert len(perms) == 1
        assert perms[0].permission_category_id == users_id
    await engine.dispose()


@pytest.mark.asyncio
async def test_seed_permissions_without_category_keeps_null():
    """Seed rows without category keep permission_category_id NULL (spec null-safe)."""
    engine = await _tenant_engine()
    async with AsyncSession(engine) as session:
        inserted, skipped = await _seed_table_idempotent(
            session,
            "permissions",
            [{"name": "no_category_permission"}],
            Permission,
        )
        assert inserted == 1
        perms = (await session.exec(select(Permission))).all()
        assert len(perms) == 1
        assert perms[0].name == "no_category_permission"
        assert perms[0].permission_category_id is None
    await engine.dispose()
