from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from pgsqlasync2fast_fastapi import create_database, drop_database
from pgsqlasync2fast_fastapi.connection import get_manager
from pgsqlasync2fast_fastapi.settings import settings as db_settings, DatabaseConnectionSettings

from ..settings import settings as tenant_settings
from ..models.bases import tenant_metadata

# Force import of all tenant models to ensure they register with MetaData
from ..models.role_model import TenantRole
from ..models.permission_model import TenantPermission
from ..models.tenant_user_model import TenantUser
from ..models.route_model import TenantRoute
from ..models.assignments_model import (
    TenantUserRole,
    TenantRolePermission,
    TenantPermissionRoute,
    TenantUserPermission
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _tenant_db_name(tenant_id: int) -> str:
    """Standard naming convention for tenant databases."""
    return f"tenant_{tenant_id}"


def get_tenant_db_url(tenant_database_name: str) -> str:
    """
    Construct the database URL for a specific tenant.
    Uses the same driver and credentials as the Auth DB but a different database name.
    """
    manager = get_manager()
    try:
        # Use the 'auth' connection as the template
        auth_url = manager.config.get_connection_url("auth")
        # Swap the database name at the end of the URL
        base_url, _ = auth_url.rsplit("/", 1)
        return f"{base_url}/{tenant_database_name}"
    except Exception:
        # Fallback to current settings
        base_url = db_settings.get_connection_url() # Uses default
        base_url, _ = base_url.rsplit("/", 1)
        return f"{base_url}/{tenant_database_name}"


def get_tenant_engine(tenant_id: int):
    """
    Get or create an async engine for a specific tenant.
    The engine is cached in the global connection manager to avoid overhead.
    """
    manager = get_manager()
    conn_name = f"tenant_{tenant_id}"

    # Check if engine already exists in manager's engine cache
    if conn_name in manager._engines:
        return manager._engines[conn_name]
    
    # Or if connection is configured in settings
    if manager.config.has_connection(conn_name):
        return manager.get_engine(conn_name)

    raise ValueError(f"Engine for tenant {tenant_id} not initialized. Use register_tenant_engine first.")


async def register_tenant_engine(tenant_id: int, database_name: str):
    """
    Register a tenant-specific engine in the global manager.
    """
    manager = get_manager()
    conn_name = f"tenant_{tenant_id}"
    
    if manager.config.has_connection(conn_name):
        return manager.get_engine(conn_name)
    
    # Get auth config as template
    try:
        auth_conn = manager.config.get_connection("auth")
    except ValueError:
        # Fallback to default if 'auth' not found
        auth_conn = manager.config.get_connection()

    # Register the connection in the manager
    tenant_conn = DatabaseConnectionSettings(
        host=auth_conn.host,
        port=auth_conn.port,
        username=auth_conn.username,
        password=auth_conn.password,
        database=database_name,
        pool_size=tenant_settings.max_tenant_connections,
        max_overflow=10, # Default value
        echo=auth_conn.echo
    )
    
    # Inject into manager's config
    manager.config.connections[conn_name] = tenant_conn
    
    # Now get_engine will find it in config and create it
    return manager.get_engine(conn_name)


# ── Database Operations ────────────────────────────────────────────────────────

async def create_tenant_database(tenant_id: int) -> str:
    """
    Create a new physical database for a tenant.
    Returns the name of the created database.
    """
    # 1. Get tenant details from Auth DB
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlmodel import select
    from ..models.tenant_model import Tenant
    
    auth_engine = get_manager().get_engine("auth")
    async with AsyncSession(auth_engine) as session:
        result = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()
        
        # If tenant not found, use naming convention (for some standalone tests)
        db_name = tenant.database_name if tenant else _tenant_db_name(tenant_id)
        
        # 2. Create the database using pgsqlasync2fast logic
        await create_database(db_name, connection_name="auth")
        
        # 3. Register the engine for future use
        await register_tenant_engine(tenant_id, db_name)
        
        print(f"✅ Database '{db_name}' created successfully")
        return db_name


async def initialize_tenant_schema(tenant_id: int, metadata: MetaData = tenant_metadata):
    # Ensure models are loaded
    from ..utils.models_loader import import_tenant_models
    import_tenant_models()
    
    engine = get_tenant_engine(tenant_id)

    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)

    print(f"✅ Initialized schema for tenant {tenant_id}")


async def get_tenant_session(tenant_id: int) -> AsyncSession:
    """
    Get a new AsyncSession for a specific tenant.
    """
    engine = get_tenant_engine(tenant_id)
    return AsyncSession(engine, expire_on_commit=False)


async def delete_tenant_database(tenant_id: int):
    """
    Drop a tenant's physical database and remove its engine from cache.
    """
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlmodel import select
    from ..models.tenant_model import Tenant
    
    auth_engine = get_manager().get_engine("auth")
    async with AsyncSession(auth_engine) as session:
        result = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()
        
        db_name = tenant.database_name if tenant else _tenant_db_name(tenant_id)
        
        # 1. Dispose engine
        await dispose_tenant_engine(tenant_id)
        
        # 2. Drop database
        await drop_database(db_name, connection_name="auth")
        
        print(f"✅ Database '{db_name}' dropped successfully")


async def dispose_tenant_engine(tenant_id: int):
    """
    Remove a tenant engine from the manager and dispose it.
    """
    manager = get_manager()
    conn_name = f"tenant_{tenant_id}"
    
    if conn_name in manager._engines:
        engine = manager._engines[conn_name]
        await engine.dispose()
        # Remove from cache
        del manager._engines[conn_name]
        if conn_name in manager._session_makers:
            del manager._session_makers[conn_name]
        print(f"🗑️  Disposed engine for tenant {tenant_id}")
    
    # Also remove from config to allow re-registration with different DB name if needed
    if manager.config.has_connection(conn_name):
        del manager.config.connections[conn_name]
