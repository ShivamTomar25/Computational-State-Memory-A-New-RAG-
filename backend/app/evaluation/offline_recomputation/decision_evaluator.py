from __future__ import annotations

import re
from typing import Any


LABELS = {
    "diagnose": ["diagnosis", "diagnose", "condition"],
    "treat": ["treat", "therapy", "medication", "dose"],
    "monitor": ["monitor", "follow", "repeat", "recheck", "surveillance"],
    "refer": ["refer", "consult", "specialist"],
    "rule_out": ["rule out", "exclude", "not supported", "unlikely"],
}


def expected_labels(truth: Any, question: Any) -> set[str]:
    payload = getattr(truth, "truth", None) or {}
    labels = set(str(item).lower() for item in payload.get("decision_labels") or [])
    if question.expected_decision_type:
        labels.add(str(question.expected_decision_type).lower())
    return labels


def predicted_labels(answer: str) -> set[str]:
    text = answer.lower()
    labels = set()
    for label, markers in LABELS.items():
        if any(marker in text for marker in markers):
            labels.add(label)
    return labels


def decision_f1(answer: str, truth: Any, question: Any) -> tuple[float | None, str, set[str], set[str]]:
    expected = expected_labels(truth, question)
    predicted = predicted_labels(answer)
    if not expected:
        return None, "missing_expected_decision_labels", expected, predicted
    if not predicted:
        return 0.0, "no_decision_label_extracted_from_answer", expected, predicted
    tp = len(expected & predicted)
    precision = tp / len(predicted) if predicted else 0.0
    recall = tp / len(expected) if expected else 0.0
    value = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return value, "controlled_label_f1_from_stored_answer", expected, predicted

