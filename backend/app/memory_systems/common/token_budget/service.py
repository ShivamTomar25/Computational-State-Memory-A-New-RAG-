from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class BudgetResult:
    included: list
    excluded_count: int
    token_count: int
    counter_provider: str


def estimate_tokens(text: str) -> int:
    return max(1, (len(text or "") + 3) // 4)


def apply_token_budget(items: Iterable, *, token_budget: int) -> BudgetResult:
    included = []
    total = 0
    excluded = 0

    for item in items:
        token_count = getattr(item, "token_count", None)

        if token_count is None and isinstance(item, dict):
            token_count = item.get("token_count")

        token_count = int(token_count or estimate_tokens(getattr(item, "content", "") or ""))

        if total + token_count > token_budget:
            excluded += 1
            continue

        included.append(item)
        total += token_count

    return BudgetResult(
        included=included,
        excluded_count=excluded,
        token_count=total,
        counter_provider="character_estimate_v1",
    )
