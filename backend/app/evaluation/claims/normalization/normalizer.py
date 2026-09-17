from __future__ import annotations

import re
from typing import Any, Optional

from app.evaluation.claims.schemas.claim import NormalizedClaim


def normalize_truth_claim(claim: dict) -> NormalizedClaim:
    if not isinstance(claim, dict):
        text = normalize_text(claim)
        return NormalizedClaim(
            claim_id=text[:120],
            claim_text=text,
            subject=text,
            predicate="claim",
            value=text,
            status="required",
            negation=False,
            confidence=None,
            citation_ids=(),
        )

    return NormalizedClaim(
        claim_id=str(claim.get("claim_id") or ""),
        claim_text=normalize_text(claim.get("claim_text") or claim.get("answer_summary") or ""),
        subject=normalize_text(claim.get("subject") or ""),
        predicate=normalize_text(claim.get("predicate") or ""),
        value=normalize_text(
            claim.get("normalized_value")
            or claim.get("value")
            or claim.get("object")
            or claim.get("expected_value")
            or ""
        ),
        status=normalize_text(claim.get("status") or claim.get("expected_status") or ""),
        negation=bool(claim.get("negation", False)),
        confidence=_optional_float(claim.get("confidence")),
        citation_ids=normalize_citation_ids(
            claim.get("required_citation_ids")
            or claim.get("supporting_source_ids")
            or claim.get("relevant_source_ids")
            or []
        ),
    )


def normalize_generated_claim(claim: Any) -> NormalizedClaim:
    normalized = _get(claim, "normalized_claim", {}) or {}
    citation_ids = _get(claim, "citation_ids", None)
    claim_text = normalize_text(_get(claim, "claim_text", "") or normalized.get("claim_text") or "")
    subject = normalize_text(normalized.get("subject") or _get(claim, "subject", "") or "")
    predicate = normalize_text(normalized.get("predicate") or _get(claim, "predicate", "") or "")
    value = normalize_text(
        normalized.get("normalized_value")
        or normalized.get("value")
        or normalized.get("object")
        or _get(claim, "normalized_value", None)
        or _get(claim, "value", None)
        or ""
    )

    if claim_text and not any((subject, predicate, value)):
        subject = claim_text
        predicate = "claim"
        value = claim_text

    return NormalizedClaim(
        claim_id=str(_get(claim, "claim_id", "") or ""),
        claim_text=claim_text,
        subject=subject,
        predicate=predicate,
        value=value,
        status=normalize_text(normalized.get("status") or _get(claim, "status", "") or ""),
        negation=bool(normalized.get("negation", _get(claim, "negation", False))),
        confidence=_optional_float(normalized.get("confidence", _get(claim, "confidence", None))),
        citation_ids=normalize_citation_ids(citation_ids or normalized.get("citation_ids") or []),
        source_support_status=normalize_text(_get(claim, "source_support_status", None) or "") or None,
    )


def normalize_citation_ids(citations: Any) -> tuple[str, ...]:
    if citations is None:
        return ()

    if isinstance(citations, (str, int)):
        return (str(citations),)

    normalized_ids = []

    for citation in citations:
        if isinstance(citation, dict):
            values = [
                citation.get("canonical_source_id"),
                citation.get("source_id"),
                citation.get("citation_id"),
                citation.get("id"),
                citation.get("document_id"),
            ]
        else:
            values = [citation]

        for value in values:
            if value is not None:
                normalized_ids.append(str(value))

    return tuple(dict.fromkeys(normalized_ids))


def normalize_text(value: Any) -> str:
    if value is None:
        return ""

    text = str(value).lower().strip()
    text = re.sub(r"[^a-z0-9.%/+-]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def claim_key(claim: NormalizedClaim) -> tuple[str, str, str, str, bool]:
    return (claim.subject, claim.predicate, claim.value, claim.status, claim.negation)


def _get(source: Any, field: str, default: Any = None) -> Any:
    if isinstance(source, dict):
        return source.get(field, default)

    return getattr(source, field, default)


def _optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None

    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None

    if parsed < 0:
        return 0.0

    if parsed > 1:
        return 1.0

    return parsed
