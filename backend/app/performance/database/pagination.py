from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CursorPage:
    items: list
    next_cursor: Optional[str]
    has_more: bool


def bounded_limit(value: Optional[int], *, default: int = 25, maximum: int = 100) -> int:
    if value is None:
        return default

    return max(1, min(value, maximum))
