from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class NormalizedClaim:
    claim_id: str
    claim_text: str
    subject: str
    predicate: str
    value: str
    status: str
    negation: bool
    confidence: Optional[float]
    citation_ids: tuple[str, ...]
    source_support_status: Optional[str] = None


@dataclass(frozen=True)
class ClaimMatch:
    generated: NormalizedClaim
    truth: Optional[NormalizedClaim]
    score: float
    matched: bool
    reason: str
