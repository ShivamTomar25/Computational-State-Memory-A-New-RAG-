from __future__ import annotations

from app.evaluation.claims.matching.matcher import match_claims
from app.evaluation.claims.normalization.normalizer import normalize_citation_ids, normalize_generated_claim, normalize_truth_claim
from app.evaluation.metrics.calculators.common import f1_score, measured_ratio, measured_value, not_applicable
from app.evaluation.metrics.calculators.context import EvaluationTurnContext
from app.evaluation.metrics.interface.base import MetricCalculation


SUPPORT_SUPPORTED = {"supported", "entailed", "correct"}
SUPPORT_UNSUPPORTED = {"unsupported", "unverifiable"}
SUPPORT_CONTRADICTED = {"contradicted", "contradiction"}


def calculate_claim_metric_group(contexts: list[EvaluationTurnContext]) -> dict[str, MetricCalculation]:
    classifications = classify_claims(contexts)
    generated_count = len(classifications["generated"])
    truth_count = classifications["truth_count"]
    supported_count = len([item for item in classifications["claims"] if item["support_status"] == "supported"])
    unsupported_count = len([item for item in classifications["claims"] if item["support_status"] == "unsupported"])
    contradicted_count = len([item for item in classifications["claims"] if item["support_status"] == "contradicted"])
    hallucinated_count = unsupported_count + contradicted_count

    results = {
        "answer_accuracy": f1_score(classifications["matched_count"], generated_count, truth_count),
        "hallucination_rate": measured_ratio(
            hallucinated_count,
            generated_count,
            {"unsupported": unsupported_count, "contradicted": contradicted_count},
        )
        if generated_count
        else not_applicable("no_generated_claims"),
        "evidence_support_rate": measured_ratio(
            supported_count,
            generated_count,
            {"supported": supported_count, "generated_claims": generated_count},
        )
        if generated_count
        else not_applicable("no_generated_claims"),
        "unsupported_claim_rate": measured_ratio(
            unsupported_count,
            generated_count,
            {"unsupported": unsupported_count, "generated_claims": generated_count},
        )
        if generated_count
        else not_applicable("no_generated_claims"),
        "expected_calibration_error": calculate_expected_calibration_error(classifications["claims"]),
    }

    results.update(calculate_citation_metrics(contexts, classifications))
    return results


def classify_claims(contexts: list[EvaluationTurnContext]) -> dict:
    generated_claims = []
    truth_claims = []
    truth_claims_by_turn = {}

    for context in contexts:
        truth_items = get_truth_claims(context)
        normalized_truth = [normalize_truth_claim(item) for item in truth_items]
        truth_claims_by_turn[getattr(context.turn, "id")] = normalized_truth
        truth_claims.extend(normalized_truth)
        generated_claims.extend(normalize_generated_claim(claim) for claim in context.claims)

    matches = match_claims(generated_claims, truth_claims)
    classified_claims = []

    for match in matches:
        explicit_status = match.generated.source_support_status

        if explicit_status in SUPPORT_SUPPORTED:
            support_status = "supported"
        elif explicit_status in SUPPORT_CONTRADICTED:
            support_status = "contradicted"
        elif explicit_status in SUPPORT_UNSUPPORTED:
            support_status = "unsupported"
        elif match.matched:
            support_status = "supported"
        else:
            support_status = "unsupported"

        classified_claims.append(
            {
                "claim_id": match.generated.claim_id,
                "claim_text": match.generated.claim_text,
                "citation_ids": list(match.generated.citation_ids),
                "confidence": match.generated.confidence,
                "support_status": support_status,
                "match_score": match.score,
                "matched_ground_truth_claim_id": match.truth.claim_id if match.truth else None,
                "match_reason": match.reason,
            }
        )

    return {
        "generated": generated_claims,
        "truth": truth_claims,
        "truth_count": len(truth_claims),
        "matched_count": len([match for match in matches if match.matched]),
        "claims": classified_claims,
        "truth_by_turn": truth_claims_by_turn,
    }


def calculate_expected_calibration_error(classified_claims: list[dict]) -> MetricCalculation:
    claims_with_confidence = [claim for claim in classified_claims if claim.get("confidence") is not None]

    if not claims_with_confidence:
        return not_applicable("missing_generated_confidence")

    bins = [[] for _ in range(10)]

    for claim in claims_with_confidence:
        confidence = claim["confidence"]
        index = min(9, int(confidence * 10))
        bins[index].append((confidence, 1.0 if claim["support_status"] == "supported" else 0.0))

    weighted_error = 0.0
    reliability = []

    for index, items in enumerate(bins):
        if not items:
            continue

        average_confidence = sum(item[0] for item in items) / len(items)
        empirical_accuracy = sum(item[1] for item in items) / len(items)
        bin_weight = len(items) / len(claims_with_confidence)
        weighted_error += bin_weight * abs(average_confidence - empirical_accuracy)
        reliability.append(
            {
                "bin": index,
                "count": len(items),
                "average_confidence": average_confidence,
                "empirical_accuracy": empirical_accuracy,
            }
        )

    return measured_value(weighted_error, {"reliability": reliability}, numerator=weighted_error, denominator=1.0)


def calculate_citation_metrics(contexts: list[EvaluationTurnContext], classifications: dict) -> dict[str, MetricCalculation]:
    generated_citations = get_generated_citation_ids(contexts)
    expected_citations = get_expected_source_ids(contexts)
    valid_context_ids = get_valid_context_source_ids(contexts) | expected_citations

    fabricated = [citation for citation in generated_citations if citation not in valid_context_ids]
    supported_by_context = [
        claim
        for claim in classifications["claims"]
        if set(claim.get("citation_ids") or []) & valid_context_ids
    ]

    results = {
        "fabricated_citation_rate": measured_ratio(
            len(fabricated),
            len(generated_citations),
            {
                "fabricated_citation_ids": fabricated,
                "generated_citation_ids": sorted(generated_citations),
                "valid_context_ids": sorted(valid_context_ids),
            },
        )
        if generated_citations
        else not_applicable("no_generated_citations"),
        "lineage_citation_f1": calculate_set_f1(generated_citations, expected_citations, "citation"),
        "faithfulness": measured_ratio(
            len(supported_by_context),
            len(classifications["claims"]),
            {"claims_supported_by_supplied_context": len(supported_by_context)},
        )
        if classifications["claims"] and valid_context_ids
        else not_applicable("missing_claims_or_supplied_context"),
        "groundedness": measured_ratio(
            len(supported_by_context),
            len(classifications["claims"]),
            {"source_validity_checked": True, "lineage_checked": True},
        )
        if classifications["claims"] and valid_context_ids
        else not_applicable("missing_claims_or_valid_lineage"),
    }
    return results


def calculate_set_f1(generated: set[str], expected: set[str], label: str) -> MetricCalculation:
    if not expected and not generated:
        return not_applicable(f"no_{label}s_available")

    true_positive = len(generated & expected)
    return f1_score(true_positive, len(generated), len(expected))


def get_truth_claims(context: EvaluationTurnContext) -> list[dict]:
    truth = getattr(context.ground_truth, "truth", None) or {}
    return truth.get("claims") or truth.get("required_claims") or []


def get_expected_source_ids(contexts: list[EvaluationTurnContext]) -> set[str]:
    expected = set()

    for context in contexts:
        truth = getattr(context.ground_truth, "truth", None) or {}
        expected.update(str(item) for item in truth.get("relevant_source_ids") or [])
        expected.update(str(item) for item in truth.get("expected_citations") or [])

        for claim in truth.get("claims") or []:
            expected.update(str(item) for item in claim.get("relevant_source_ids") or [])
            expected.update(str(item) for item in claim.get("required_citation_ids") or [])
            expected.update(str(item) for item in claim.get("supporting_source_ids") or [])

    return expected


def get_valid_context_source_ids(contexts: list[EvaluationTurnContext]) -> set[str]:
    valid_ids = set()

    for context in contexts:
        for item in context.retrieval_items:
            canonical_source_id = getattr(item, "canonical_source_id", None)
            document_id = getattr(item, "document_id", None)
            section_id = getattr(item, "section_id", None)

            for value in (canonical_source_id, document_id, section_id):
                if value is not None:
                    valid_ids.add(str(value))

    return valid_ids


def get_generated_citation_ids(contexts: list[EvaluationTurnContext]) -> set[str]:
    citation_ids = set()

    for context in contexts:
        if context.output is not None:
            citation_ids.update(normalize_citation_ids(getattr(context.output, "citations", None)))

        for claim in context.claims:
            citation_ids.update(normalize_citation_ids(getattr(claim, "citation_ids", None)))

    return citation_ids
