"""Migration test: adopt uuid7 literals on an existing tenant database (SQLite)."""

from __future__ import annotations

import json
import os
from uuid import UUID, uuid4

import pytest
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

from tenant2fast_fastapi.models.bases import tenant_metadata
from tenant2fast_fastapi.models.permission_category_model import Category
from tenant2fast_fastapi.models.permission_model import Permission
from tenant2fast_fastapi.models.role_model import Role
from tenant2fast_fastapi.seeders import (
    TENANT_RBAC_MANIFEST_PATH,
    adopt_explicit_seed_ids,
)


def _literals() -> dict[str, dict[str, dict]]:
    """Load seed literals keyed by table then name."""
    base = os.path.join(os.path.dirname(TENANT_RBAC_MANIFEST_PATH), "boot")
    out: dict[str, dict[str, dict]] = {}
    for table in ("categories", "roles", "permissions"):
        rows = json.load(open(os.path.join(base, f"{table}.json")))
        out[table] = {row["name"]: row for row in rows}
    return out


@pytest.mark.asyncio
async def test_adopt_explicit_ids_migrates_existing_rows():
    literals = _literals()
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(tenant_metadata.create_all)

    old_cat, old_role, old_perm = uuid4(), uuid4(), uuid4()
    async with AsyncSession(engine) as session:
        session.add(Category(id=old_cat, name="System"))
        session.add(Role(id=old_role, name="Owner"))
        session.add(
            Permission(
                id=old_perm,
                name="view_tenant_info",
                permission_category_id=old_cat,
            )
        )
        await session.commit()

    async with AsyncSession(engine) as session:
        remaps = await adopt_explicit_seed_ids(session, profile="dev")
        assert len(remaps) == 3
        await session.commit()

    async with AsyncSession(engine) as session:
        cats = (await session.execute(select(Category))).scalars().all()
        roles = (await session.execute(select(Role))).scalars().all()
        perms = (await session.execute(select(Permission))).scalars().all()

        assert len(cats) == 1 and len(roles) == 1 and len(perms) == 1
        assert cats[0].id == UUID(literals["categories"]["System"]["id"])
        assert roles[0].id == UUID(literals["roles"]["Owner"]["id"])
        assert perms[0].id == UUID(literals["permissions"]["view_tenant_info"]["id"])

        expected_cat = UUID(literals["categories"]["System"]["id"])
        assert perms[0].permission_category_id == expected_cat

    # Idempotent: second run is a no-op.
    async with AsyncSession(engine) as session:
        assert await adopt_explicit_seed_ids(session, profile="dev") == []
        await session.commit()

    await engine.dispose()
