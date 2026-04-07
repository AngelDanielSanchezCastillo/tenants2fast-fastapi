"""Utilities for tenant2fast-fastapi"""

# Import cache utilities from permissions2fast (shared Redis configuration)
from permissions2fast_fastapi.utils import (
    cache_tenant_data,
    get_tenant_data,
    get_redis_client,
    close_redis_client,
)

__all__ = [
    "cache_tenant_data",
    "get_tenant_data",
    "get_redis_client",
    "close_redis_client",
]
