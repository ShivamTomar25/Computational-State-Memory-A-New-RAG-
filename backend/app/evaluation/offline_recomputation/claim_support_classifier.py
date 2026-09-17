from __future__ import annotations

from app.evaluation.offline_recomputation.claim_matcher import ClaimMatchResult, claim_text, has_uncertainty
from app.evaluation.offline_recomputation.citation_resolver import CitationResolution


ALLOWED = {
    "supported",
    "partially_supported",
    "unsupported",
    "contradicted",
    "not_factual",
    "insufficient_evidence_statement",
}


def classify_claim(claim, match: ClaimMatchResult | None, citations: list[CitationResolution]) -> tuple[str, str]:
    text = claim_text(claim).lower()
    stored = str(getattr(claim, "source_support_status", "") or "").lower().strip()
    if "insufficient evidence" in text or "not enough evidence" in text or "cannot determine" in text:
        return "insufficient_evidence_statement", "answer_explicitly_states_insufficient_evidence"
    if not text or all(token in {"yes", "no", "unknown"} for token in text.split()):
        return "not_factual", "not_a_factual_clinical_claim"
    if "contradict" in stored:
        return "contradicted", "stored_claim_status_contradicted"
    valid_citations = [row for row in citations if row.classification.startswith("valid")]
    if match and match.correctness and valid_citations:
        return "supported", "matched_expected_claim_and_has_valid_citation"
    if match and match.correctness:
        return "partially_supported", "matched_expected_claim_but_no_resolved_supporting_citation"
    if valid_citations and has_uncertainty(text):
        return "partially_supported", "uncertain_claim_with_valid_context"
    if valid_citations:
        return "partially_supported", "has_valid_context_but_no_expected_claim_match"
    if stored in {"unsupported", "unverifiable"}:
        return "unsupported", "stored_unsupported_and_no_resolved_support"
    return "unsupported", "no_expected_claim_match_or_resolved_support"

