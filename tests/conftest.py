"""
conftest.py for tenants2fast-fastapi tests.

Setup for testing both Auth and Tenant databases with Redis/RBAC integration.
"""

import asyncio
import os
import pytest

# Ensure the auth connection is treated as a superuser for database creation/dropping in tests
os.environ["DB_CONNECTIONS__AUTH__IS_SUPERUSER"] = "true"

from typing import AsyncGenerator, Generator
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy import text
from sqlmodel import select

from oauth2fast_fastapi import (
    startup_database,
    shutdown_database,
    AuthModel,
    User,
)
from pgsqlasync2fast_fastapi.connection import get_manager
from tenant2fast_fastapi.models.tenant_model import Tenant
from tenant2fast_fastapi.models.user_tenant_model import UserTenant
from tenant2fast_fastapi.databases.tenant_db_factory import (
    create_tenant_database,
    initialize_tenant_schema,
    get_tenant_session,
    delete_tenant_database,
)
from tenant2fast_fastapi.services.tenant_rbac_seeder import seed_tenant_rbac


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create a single event loop for the whole test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def db_engine():
    """
    Initialize the auth database once per session.
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
    Provide a transactional session per test for the Auth DB.
    Truncates all tables before each test for isolation.
    """
    async with db_engine.begin() as conn:
        tables = list(AuthModel.metadata.tables.keys())
        if tables:
            table_names = ", ".join([f'"{t}"' for t in tables])
            await conn.execute(
                text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE")
            )

    async with AsyncSession(db_engine, expire_on_commit=False) as db_session:
        try:
            yield db_session
        finally:
            await db_session.close()


@pytest.fixture
async def test_user(session: AsyncSession) -> User:
    """Create a basic test user in Auth DB."""
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
async def test_tenant(session: AsyncSession) -> Tenant:
    """
    Create a basic test tenant in Auth DB and its dedicated database.
    Initializes the schema and runs the RBAC seeder.
    """
    import uuid
    slug = f"acme-{uuid.uuid4().hex[:6]}"
    tenant = Tenant(
        name="ACME Corp",
        slug=slug,
        database_name=f"test_db_{slug.replace('-', '_')}",
        is_active=True,
    )
    session.add(tenant)
    await session.commit()
    await session.refresh(tenant)

    # Provision tenant DB
    await create_tenant_database(tenant.id)
    await initialize_tenant_schema(tenant.id)
    await seed_tenant_rbac(tenant.id)

    yield tenant

    # Cleanup tenant DB
    await delete_tenant_database(tenant.id)


@pytest.fixture
async def user_tenant_link(session: AsyncSession, test_user: User, test_tenant: Tenant) -> UserTenant:
    """Link the test user to the test tenant in the Auth DB."""
    link = UserTenant(user_id=test_user.id, tenant_id=test_tenant.id)
    session.add(link)
    await session.commit()
    await session.refresh(link)
    return link


@pytest.fixture
async def tenant_session(test_tenant: Tenant) -> AsyncGenerator[AsyncSession, None]:
    """Provide a session for the dedicated tenant database."""
    session = await get_tenant_session(test_tenant.id)
    async with session:
        yield session


@pytest.fixture
async def redis_client():
    """
    Yields a redis client if TENANT_REDIS_URL is configured.
    Otherwise skips the test.
    """
    from tenant2fast_fastapi.settings import settings
    import redis.asyncio as redis

    if not settings.redis_url:
        pytest.skip("Redis not configured")

    client = redis.from_url(settings.redis_url, decode_responses=True)
    yield client
    await client.close()


@pytest.fixture
async def flush_redis(redis_client):
    """Flush redis before each test to ensure isolation."""
    await redis_client.flushdb()
