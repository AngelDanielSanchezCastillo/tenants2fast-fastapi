import json
from typing import List, Optional
from ..settings import settings


# Try to import redis, but don't fail if not present
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


def _get_redis_client():
    """Internal helper to get a redis client if available and configured."""
    if not REDIS_AVAILABLE or not settings.redis_url:
        return None
    return redis.from_url(settings.redis_url, decode_responses=True)


async def get_tenant_user_permissions_cache(tenant_id: int, user_id: int) -> Optional[List[dict]]:
    """
    Get tenant user permissions from Redis cache.
    Returns None if cache miss or Redis unavailable.
    """
    client = _get_redis_client()
    if not client:
        return None

    try:
        key = f"tenant:{tenant_id}:user:{user_id}:permissions"
        data = await client.get(key)
        if data:
            return json.loads(data)
    except Exception:
        # Silently fail on Redis errors to falling back to DB
        pass
    return None


async def set_tenant_user_permissions_cache(
    tenant_id: int, user_id: int, permissions: List[dict], ttl: int = None
):
    """
    Store tenant user permissions in Redis cache.
    """
    client = _get_redis_client()
    if not client:
        return

    try:
        key = f"tenant:{tenant_id}:user:{user_id}:permissions"
        time_to_live = ttl or settings.redis_ttl
        await client.set(key, json.dumps(permissions), ex=time_to_live)
    except Exception:
        pass


async def invalidate_tenant_user_cache(tenant_id: int, user_id: int):
    """
    Invalidate the permissions cache for a specific user in a tenant.
    Called when roles or permissions are modified.
    """
    client = _get_redis_client()
    if not client:
        return

    try:
        key = f"tenant:{tenant_id}:user:{user_id}:permissions"
        await client.delete(key)
    except Exception:
        pass


async def get_user_tenant_cache(user_id: int) -> Optional[int]:
    """Get the cached tenant_id for a global user."""
    client = _get_redis_client()
    if not client:
        return None
    try:
        data = await client.get(f"user:{user_id}:tenant_id")
        return int(data) if data else None
    except Exception:
        return None


async def set_user_tenant_cache(user_id: int, tenant_id: int, ttl: int = 3600):
    """Cache the tenant_id for a global user."""
    client = _get_redis_client()
    if not client:
        return
    try:
        await client.set(f"user:{user_id}:tenant_id", tenant_id, ex=ttl)
    except Exception:
        pass


async def get_tenant_data_cache(tenant_id: int) -> Optional[dict]:
    """Get the cached data for a tenant (Auth DB record)."""
    client = _get_redis_client()
    if not client:
        return None
    try:
        data = await client.get(f"tenant:{tenant_id}:data")
        return json.loads(data) if data else None
    except Exception:
        return None


async def set_tenant_data_cache(tenant_id: int, data: dict, ttl: int = 3600):
    """Cache the auth data for a tenant."""
    client = _get_redis_client()
    if not client:
        return
    try:
        await client.set(f"tenant:{tenant_id}:data", json.dumps(data), ex=ttl)
    except Exception:
        pass
