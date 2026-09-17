from __future__ import annotations

from typing import Optional, Protocol


class CacheBackend(Protocol):
    def get(self, key: str):
        ...

    def set(self, key: str, value, ttl_seconds: Optional[int] = None) -> None:
        ...

    def delete(self, key: str) -> None:
        ...

    def delete_prefix(self, prefix: str) -> int:
        ...

    def clear(self) -> None:
        ...

    def stats(self) -> dict:
        ...
