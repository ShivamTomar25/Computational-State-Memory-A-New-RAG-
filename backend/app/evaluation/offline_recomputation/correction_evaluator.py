from __future__ import annotations

import re


CORRECTION_MARKERS = [
    "corrected creatinine 1.5",
    "1.5 mg/dl",
    "egfr 53",
    "53 ml/min",
    "follow-up creatinine 1.2",
    "1.2 mg/dl",
    "egfr 70",
    "70 ml/min",
    "severe ckd",
]


def is_correction_question(question, truth) -> bool:
    payload = getattr(truth, "truth", None) or {}
    text = f"{question.question} {payload}".lower()
    return bool(re.search(r"\b(correct|corrected|follow|repeat|creatinine|egfr|ckd)\b", text))


def correction_score(answer: str, question, truth) -> tuple[float | None, str]:
    if not is_correction_question(question, truth):
        return None, "no_correction_case"
    text = answer.lower()
    positive_markers = ["1.5", "53", "1.2", "70", "corrected", "follow"]
    hits = sum(1 for marker in positive_markers if marker in text)
    severe_ckd_penalty = 1 if ("severe ckd" in text or "severe chronic kidney disease" in text) and "not" not in text else 0
    return max(0.0, min(1.0, hits / 4 - severe_ckd_penalty * 0.5)), "deterministic_correction_marker_score"


def required_csm_sanity_terms() -> list[str]:
    return CORRECTION_MARKERS

