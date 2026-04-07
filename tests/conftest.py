"""
conftest.py for tenants2fast-fastapi tests.

Reuses the oauth2fast-fastapi DB bootstrap pattern from permissions2fast-fastapi.
The .env file in the project root provides all required environment variables.
"""

import asyncio
from typing import AsyncGenerator, Generator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from sqlmodel import SQLModel

from oauth2fast_fastapi import (
    startup_database,
    shutdown_database,
    AuthModel,
)
from pgsqlasync2fast_fastapi.connection import get_manager

# ── Import all models that must be registered in AuthModel.metadata ──────────
# These come transitively via permissions2fast-fastapi and tenants2fast-fastapi.
from oauth2fast_fastapi.models import user_model  # noqa: F401 – registers User
from tenant2fast_fastapi.models import tenant_model, user_tenant_model  # noqa: F401

# We rely on pydantic-settings + .env to load the configuration automatically.


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create a single event loop for the whole test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def db_engine():
    """
    Initialise the auth database once per session.
    Drops and recreates the public schema to ensure a clean slate.
    """
    await startup_database()

    manager = get_manager()
    engine = manager.get_engine("auth")

    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE;"))
        await conn.execute(text("CREATE SCHEMA public;"))
        await conn.execute(text("GRANT ALL ON SCHEMA public TO public;"))
        await conn.run_sync(AuthModel.metadata.create_all)

    yield engine

    await shutdown_database()


@pytest.fixture(scope="function")
async def session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a transactional session per test.
    Truncates all tables before each test for isolation.
    """
    async with db_engine.begin() as conn:
        tables = list(AuthModel.metadata.tables.keys())
        if tables:
            table_names = ", ".join([f'"{t}"' for t in tables])
            await conn.execute(
                text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE")
            )

    connection = await db_engine.connect()
    transaction = await connection.begin()
    db_session = AsyncSession(bind=connection, expire_on_commit=False)

    try:
        yield db_session
    finally:
        await db_session.close()
        if transaction.is_active:
            await transaction.rollback()
        await connection.close()


# ── Shared fixtures ───────────────────────────────────────────────────────────

from oauth2fast_fastapi import User
from tenant2fast_fastapi.models.tenant_model import Tenant2
from tenant2fast_fastapi.models.user_tenant_model import UserTenant2


@pytest.fixture
async def test_user(session: AsyncSession) -> User:
    """Create a basic test user."""
    user = User(
        email="test@tenants2fast.dev",
        password="hashed_secret",
        name="Test Tenant User",
        is_active=True,
        is_verified=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.fixture
async def test_tenant(session: AsyncSession) -> Tenant2:
    """Create a basic test tenant."""
    tenant = Tenant2(
        name="ACME Corp",
        slug="acme-corp",
        database_name="tenant_acme",
        is_active=True,
        contact_email="admin@acme.com",
    )
    session.add(tenant)
    await session.commit()
    await session.refresh(tenant)
    return tenant
