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
