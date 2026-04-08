"""Utilities for tenant2fast-fastapi"""

from .tenant_cache import (
    get_tenant_data_cache as get_tenant_data,
    set_tenant_data_cache as cache_tenant_data,
)
from permissions2fast_fastapi.utils import (
    get_redis_client,
    close_redis_client,
)

__all__ = [
    "cache_tenant_data",
    "get_tenant_data",
    "get_redis_client",
    "close_redis_client",
]
