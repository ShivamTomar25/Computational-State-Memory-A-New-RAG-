from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


SYNONYMS = {
    "cr": "creatinine",
    "creat": "creatinine",
    "egfr": "estimated glomerular filtration rate",
    "e gfr": "estimated glomerular filtration rate",
    "renal": "kidney",
    "ckd": "chronic kidney disease",
    "not supported": "unsupported",
    "incorrect": "corrected",
    "follow up": "followup",
}


@dataclass(frozen=True)
class ClaimMatchResult:
    claim_id: str
    matched_truth_id: str | None
    matched_truth_text: str | None
    score: float
    correctness: bool
    reason: str


def expected_claims(truth: Any) -> list[dict]:
    payload = getattr(truth, "truth", None) or {}
    claims = []
    for key in ("claims", "required_claims", "expected_claims", "acceptable_claims"):
        value = payload.get(key)
        if isinstance(value, list):
            claims.extend(as_claim(item, f"{key}_{index}") for index, item in enumerate(value, start=1))
    if not claims:
        for key in ("expected_answer", "answer", "answer_summary"):
            if payload.get(key):
                claims.append(as_claim(payload[key], key))
    return claims


def match_generated_claims(generated_claims: list[Any], truth: Any) -> list[ClaimMatchResult]:
    truth_claims = expected_claims(truth)
    unused = list(truth_claims)
    results = []
    for claim in generated_claims:
        text = claim_text(claim)
        best = None
        best_score = 0.0
        for candidate in unused:
            score = semantic_score(text, candidate["text"])
            if score > best_score:
                best = candidate
                best_score = score
        correctness = best is not None and best_score >= 0.56
        if correctness and best in unused:
            unused.remove(best)
        results.append(
            ClaimMatchResult(
                claim_id=str(getattr(claim, "claim_id", "") or ""),
                matched_truth_id=best["id"] if best else None,
                matched_truth_text=best["text"] if best else None,
                score=best_score,
                correctness=correctness,
                reason="normalized_numeric_temporal_semantic_match" if correctness else "no_question_ground_truth_match",
            )
        )
    return results


def semantic_score(left: str, right: str) -> float:
    left_norm = normalize_clinical_text(left)
    right_norm = normalize_clinical_text(right)
    if not left_norm or not right_norm:
        return 0.0
    if left_norm == right_norm or left_norm in right_norm or right_norm in left_norm:
        return 1.0
    left_tokens = set(left_norm.split())
    right_tokens = set(right_norm.split())
    overlap = len(left_tokens & right_tokens) / max(1, len(left_tokens | right_tokens))
    left_numbers = set(re.findall(r"\d+(?:\.\d+)?", left_norm))
    right_numbers = set(re.findall(r"\d+(?:\.\d+)?", right_norm))
    numeric = 0.25 if left_numbers and left_numbers == right_numbers else 0.0
    negation = 0.15 if has_negation(left_norm) == has_negation(right_norm) else -0.15
    uncertainty = 0.10 if has_uncertainty(left_norm) == has_uncertainty(right_norm) else 0.0
    correction = 0.15 if has_correction(left_norm) == has_correction(right_norm) else 0.0
    return max(0.0, min(1.0, overlap + numeric + negation + uncertainty + correction))


def normalize_clinical_text(value: Any) -> str:
    text = str(value or "").lower()
    text = text.replace("m²", "m2")
    text = text.replace("m\u00b2", "m2")
    text = re.sub(r"ml/min/1\.73\s*m2", "ml min 1.73 m2", text)
    for source, target in SYNONYMS.items():
        text = re.sub(rf"\b{re.escape(source)}\b", target, text)
    text = re.sub(r"[^a-z0-9.%/+-]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def as_claim(value: Any, fallback_id: str) -> dict:
    if isinstance(value, dict):
        text = value.get("claim_text") or value.get("answer_summary") or value.get("value") or value.get("expected_value") or value
        return {"id": str(value.get("claim_id") or fallback_id), "text": normalize_claim_payload(text)}
    return {"id": fallback_id, "text": normalize_claim_payload(value)}


def normalize_claim_payload(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(str(item) for item in value.values() if item is not None)
    return str(value or "")


def claim_text(claim: Any) -> str:
    normalized = getattr(claim, "normalized_claim", None) or {}
    parts = [getattr(claim, "claim_text", "") or ""]
    if isinstance(normalized, dict):
        parts.extend(str(normalized.get(key) or "") for key in ("subject", "predicate", "value", "normalized_value", "status"))
    return " ".join(parts)


def has_negation(text: str) -> bool:
    return bool(re.search(r"\b(no|not|denies|without|negative|unsupported)\b", text))


def has_uncertainty(text: str) -> bool:
    return bool(re.search(r"\b(possible|likely|uncertain|unclear|may|might|insufficient)\b", text))


def has_correction(text: str) -> bool:
    return bool(re.search(r"\b(corrected|correction|revised|updated|followup|follow up|repeat)\b", text))

