import json
import os
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from ..models.role_model import TenantRole
from ..models.permission_category_model import TenantPermissionCategory
from ..models.permission_model import TenantPermission
from ..databases.tenant_db_factory import get_tenant_session


async def seed_tenant_rbac(tenant_id: int):
    """
    Seeder idempotente que crea los roles y permisos por defecto de un tenant.
    Se ejecuta tras crear un nuevo tenant o manualmente para actualizar schemas.
    """
    session = await get_tenant_session(tenant_id)
    async with session:
        # 1. Cargar datos del JSON
        seed_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "data",
            "seeders",
            "tenant_seed_data.json"
        )
        with open(seed_path, "r") as f:
            data = json.load(f)

        # 2. Seed Roles
        for role_data in data.get("roles", []):
            result = await session.exec(select(TenantRole).where(TenantRole.name == role_data["name"])
            )
            if not result.one_or_none():
                role = TenantRole(
                    name=role_data["name"],
                    description=role_data["description"]
                )
                session.add(role)

        # 3. Seed Categories and Permissions
        for cat_data in data.get("categories", []):
            # Find or create category
            result = await session.exec(select(TenantPermissionCategory).where(
                    TenantPermissionCategory.name == cat_data["name"]
                )
            )
            category = result.one_or_none()
            if not category:
                category = TenantPermissionCategory(name=cat_data["name"])
                session.add(category)
                await session.flush()
                await session.refresh(category)

            # Seed permissions for this category
            for perm_data in cat_data.get("permissions", []):
                result = await session.exec(select(TenantPermission).where(
                        TenantPermission.name == perm_data["name"]
                    )
                )
                if not result.one_or_none():
                    permission = TenantPermission(
                        name=perm_data["name"],
                        permission_category_id=category.id
                    )
                    session.add(permission)

        await session.commit()
    print(f"✅ Seeding completed for tenant {tenant_id}")
