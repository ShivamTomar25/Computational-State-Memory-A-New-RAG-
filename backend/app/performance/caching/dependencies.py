from __future__ import annotations

from app.config import settings
from app.performance.caching.memory_cache import memory_cache
from app.performance.caching.redis_cache import RedisCacheUnavailable


def get_cache_backend():
    if settings.cache_provider == "memory":
        return memory_cache

    return RedisCacheUnavailable("redis_dependency_not_installed")
