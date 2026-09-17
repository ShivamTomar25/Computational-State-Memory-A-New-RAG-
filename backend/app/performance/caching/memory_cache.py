from __future__ import annotations

import time
from collections import OrderedDict
from contextvars import ContextVar
from dataclasses import dataclass
from threading import Lock
from typing import Optional

from app.config import settings


request_cache_stats: ContextVar[Optional[dict]] = ContextVar("request_cache_stats", default=None)


@dataclass
class CacheEntry:
    value: object
    expires_at: float


class MemoryTTLCache:
    def __init__(self, *, max_entries: int, default_ttl_seconds: int) -> None:
        self._max_entries = max_entries
        self._default_ttl_seconds = default_ttl_seconds
        self._items: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = Lock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get(self, key: str):
        now = time.monotonic()

        with self._lock:
            entry = self._items.get(key)

            if entry is None or entry.expires_at <= now:
                if entry is not None:
                    self._items.pop(key, None)

                self._misses += 1
                record_request_cache_stat("misses")
                return None

            self._items.move_to_end(key)
            self._hits += 1
            record_request_cache_stat("hits")
            return entry.value

    def set(self, key: str, value, ttl_seconds: Optional[int] = None) -> None:
        ttl = ttl_seconds or self._default_ttl_seconds
        expires_at = time.monotonic() + ttl

        with self._lock:
            self._items[key] = CacheEntry(value=value, expires_at=expires_at)
            self._items.move_to_end(key)

            while len(self._items) > self._max_entries:
                self._items.popitem(last=False)
                self._evictions += 1

    def delete(self, key: str) -> None:
        with self._lock:
            self._items.pop(key, None)

    def delete_prefix(self, prefix: str) -> int:
        deleted = 0

        with self._lock:
            for key in list(self._items.keys()):
                if key.startswith(prefix):
                    self._items.pop(key, None)
                    deleted += 1

        return deleted

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def stats(self) -> dict:
        with self._lock:
            return {
                "provider": "memory",
                "entries": len(self._items),
                "max_entries": self._max_entries,
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
            }


def record_request_cache_stat(field: str) -> None:
    stats = request_cache_stats.get()

    if stats is not None:
        stats[field] += 1


memory_cache = MemoryTTLCache(
    max_entries=settings.cache_max_entries,
    default_ttl_seconds=settings.cache_default_ttl_seconds,
)
