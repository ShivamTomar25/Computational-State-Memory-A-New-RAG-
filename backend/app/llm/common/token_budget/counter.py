from __future__ import annotations


def estimate_llm_tokens(text: str) -> int:
    return max(1, (len(text or "") + 3) // 4)
