"""
TenantFast FastAPI Settings

Configuration for tenant2fast-fastapi module using pydantic-settings.
Reads from environment variables with TENANT_ prefix.
"""

import os

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Look for .env in the current working directory (where the app is running)
DOTENV_PATH = os.path.join(os.getcwd(), ".env")


class TenantSettings(BaseSettings):
    """Tenant management configuration settings."""
    
    model_config = SettingsConfigDict(
        env_file=DOTENV_PATH,
        env_file_encoding="utf-8",
        env_prefix="TENANT_",
        env_nested_delimiter="__",
        extra="ignore",
    )
    
    # Database prefix for tenant databases
    db_prefix: str = "tenant_"

    # URL prefix for tenant management endpoints
    url_prefix: SecretStr = SecretStr("tenants")
    
    # pgsqlasync2fast-fastapi connection settings (used for tenant database management)
    base_db_connection: SecretStr = SecretStr("tenant")
    
    # Connection pool settings
    max_tenant_connections: int = 5

    # Redis configuration for RBAC caching (optional)
    redis_url: str | None = None
    redis_ttl: int = 300  # Default 5 minutes


try:
    settings = TenantSettings()
except Exception as e:
    # Use log2fast_fastapi for proper error logging if available
    try:
        from log2fast_fastapi import get_logger
        logger = get_logger(__name__)
        logger.exception(
            "🚨 Error loading TenantFast configuration",
            extra_data={
                "error": str(e),
                "dotenv_path": DOTENV_PATH,
            },
        )
    except ImportError:
        print(f"🚨 Error loading TenantFast configuration: {e}")
    raise

