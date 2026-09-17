from __future__ import annotations


class RedisCacheUnavailable:
    def __init__(self, reason: str = "redis_cache_not_configured") -> None:
        self.reason = reason

    def get(self, key: str):
        return None

    def set(self, key: str, value, ttl_seconds=None) -> None:
        return None

    def delete(self, key: str) -> None:
        return None

    def delete_prefix(self, prefix: str) -> int:
        return 0

    def clear(self) -> None:
        return None

    def stats(self) -> dict:
        return {"provider": "redis", "status": "unavailable", "reason": self.reason}
