from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class EvaluationTurnContext:
    turn: object
    question: object
    ground_truth: Optional[object]
    output: Optional[object]
    claims: list[object]
    retrieval_items: list[object]
    llm_call: Optional[object]
