from __future__ import annotations

import re
from typing import Any


def temporal_expected(truth: Any, question: Any) -> list[str]:
    payload = getattr(truth, "truth", None) or {}
    expected = list(payload.get("temporal_assertions") or [])
    if not expected and re.search(r"\b(current|latest|before|after|follow|trend|changed|corrected)\b", question.question.lower()):
        expected.append(question.question)
    return [str(item) for item in expected]


def temporal_score(answer: str, expected: list[str]) -> tuple[float | None, str]:
    if not expected:
        return None, "missing_temporal_ground_truth"
    text = answer.lower()
    markers = ["current", "latest", "prior", "previous", "follow", "after", "before", "corrected", "repeat", "now"]
    hits = sum(1 for marker in markers if marker in text)
    if hits:
        return min(1.0, hits / 3), "temporal_markers_found_in_stored_answer"
    return 0.0, "temporal_question_without_temporal_marker_in_answer"

