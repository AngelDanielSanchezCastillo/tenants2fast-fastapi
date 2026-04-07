"""
Tenant Database Factory

Manages tenant-specific PostgreSQL databases using pgsqlasync2fast_fastapi.
Each tenant gets their own isolated database; connections are registered
dynamically into the global DatabaseManager so they can be reused.
"""

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from pgsqlasync2fast_fastapi import create_database, drop_database
from pgsqlasync2fast_fastapi.connection import get_manager
from pgsqlasync2fast_fastapi.settings import settings as db_settings

from ..settings import settings as tenant_settings


# ── MetaData ───────────────────────────────────────────────────────────────────

# MetaData exclusive for tenant-specific tables.
# All tenant models should use this metadata to ensure they are created in the
# tenant's isolated database and not in the global/auth database.
tenant_metadata = MetaData()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _tenant_connection_name(tenant_id: int) -> str:
    """Internal name used to register a tenant connection in the manager."""
    return f"tenant_{tenant_id}"


def _tenant_db_name(tenant_id: int) -> str:
    """PostgreSQL database name for a tenant."""
    return f"{tenant_settings.db_prefix}{tenant_id}"


def _build_tenant_url(tenant_id: int) -> str:
    """
    Build an asyncpg URL for a tenant's database using the superuser credentials
    that are already registered in pgsqlasync2fast_fastapi's settings.
    """
    superuser_conn = db_settings.get_superuser_connection()
    if superuser_conn is None:
        raise RuntimeError(
            "No superuser connection configured in pgsqlasync2fast_fastapi settings. "
            "Set DB_CONNECTIONS__<name>__IS_SUPERUSER=true in your .env."
        )
    db_name = _tenant_db_name(tenant_id)
    return (
        f"postgresql+asyncpg://"
        f"{superuser_conn.username}:{superuser_conn.password.get_secret_value()}@"
        f"{superuser_conn.host}:{superuser_conn.port}/{db_name}"
    )


# ── Public API ─────────────────────────────────────────────────────────────────

async def create_tenant_database(tenant_id: int) -> str:
    """
    Create a new PostgreSQL database for a tenant via pgsqlasync2fast_fastapi.

    Args:
        tenant_id: The tenant's ID.

    Returns:
        The name of the created database.

    Raises:
        RuntimeError: If no superuser connection is available.
    """
    db_name = _tenant_db_name(tenant_id)
    await create_database(db_name)
    return db_name


def get_tenant_engine(tenant_id: int):
    """
    Get (or lazily register + create) a SQLAlchemy AsyncEngine for a tenant's DB.

    The engine is registered into the global DatabaseManager so the manager
    keeps track of it and can dispose all connections at shutdown.

    Args:
        tenant_id: The tenant's ID.

    Returns:
        AsyncEngine for the tenant's database.
    """
    manager = get_manager()
    conn_name = _tenant_connection_name(tenant_id)

    # Return cached engine if already registered
    if conn_name in manager._engines:
        return manager._engines[conn_name]

    # Create engine directly (tenant connections are dynamic — not in .env)
    url = _build_tenant_url(tenant_id)
    engine = create_async_engine(
        url,
        echo=False,
        pool_size=tenant_settings.max_tenant_connections,
        max_overflow=5,
        pool_pre_ping=True,
    )

    # Register in manager so close_all() covers it too
    manager._engines[conn_name] = engine

    return engine


async def initialize_tenant_schema(tenant_id: int, metadata: MetaData = tenant_metadata):
    """
    Create all tables in a tenant's database.

    Args:
        tenant_id: The tenant's ID.
        metadata: SQLAlchemy MetaData. Defaults to the module-level tenant_metadata.
    """
    engine = get_tenant_engine(tenant_id)

    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)

    print(f"✅ Initialized schema for tenant {tenant_id}")


async def get_tenant_session(tenant_id: int) -> AsyncSession:
    """
    Create and return a new AsyncSession for a tenant's database.

    Args:
        tenant_id: The tenant's ID.

    Returns:
        A new AsyncSession. The caller is responsible for closing it.
    """
    engine = get_tenant_engine(tenant_id)
    return AsyncSession(engine, expire_on_commit=False)


async def dispose_tenant_engine(tenant_id: int):
    """
    Dispose of a tenant's engine and remove it from the manager's cache.

    Args:
        tenant_id: The tenant's ID.
    """
    manager = get_manager()
    conn_name = _tenant_connection_name(tenant_id)
    if conn_name in manager._engines:
        await manager._engines[conn_name].dispose()
        del manager._engines[conn_name]
        print(f"🗑️  Disposed engine for tenant {tenant_id}")


async def delete_tenant_database(tenant_id: int):
    """
    Drop the tenant's dedicated database. USE WITH CAUTION — irreversible!

    Args:
        tenant_id: The tenant's ID.
    """
    await dispose_tenant_engine(tenant_id)
    db_name = _tenant_db_name(tenant_id)
    await drop_database(db_name, force=True)
