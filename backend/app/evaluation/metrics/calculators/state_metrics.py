from __future__ import annotations

from app.evaluation.claims.matching.matcher import match_claims
from app.evaluation.claims.normalization.normalizer import normalize_generated_claim, normalize_truth_claim, normalize_text
from app.evaluation.metrics.calculators.claim_metrics import get_truth_claims
from app.evaluation.metrics.calculators.common import f1_score, measured_ratio, measured_value, not_applicable
from app.evaluation.metrics.calculators.context import EvaluationTurnContext
from app.evaluation.metrics.interface.base import MetricCalculation


def calculate_state_metric_group(contexts: list[EvaluationTurnContext]) -> dict[str, MetricCalculation]:
    return {
        "state_accuracy": calculate_state_accuracy(contexts),
        "decision_f1": calculate_decision_f1(contexts),
        "temporal_consistency": calculate_temporal_consistency(contexts),
        "contradiction_handling": calculate_contradiction_handling(contexts),
        "correction_recovery": calculate_correction_recovery(contexts),
        "memory_update_accuracy": calculate_memory_update_accuracy(contexts),
        "state_recovery_time": calculate_state_recovery_time(contexts),
    }


def calculate_state_accuracy(contexts: list[EvaluationTurnContext]) -> MetricCalculation:
    generated = []
    truth = []

    for context in contexts:
        generated.extend(normalize_generated_claim(claim) for claim in context.claims)
        truth.extend(normalize_truth_claim(claim) for claim in get_truth_claims(context))

    if not truth:
        return not_applicable("missing_ground_truth_state_claims")

    matches = match_claims(generated, truth)
    matched_count = len([match for match in matches if match.matched])
    return measured_ratio(
        matched_count,
        len(truth),
        {
            "matched_state_claims": matched_count,
            "expected_state_claims": len(truth),
            "generated_state_claims": len(generated),
        },
    )


def calculate_decision_f1(contexts: list[EvaluationTurnContext]) -> MetricCalculation:
    expected_labels = []
    predicted_labels = []

    for context in contexts:
        truth = getattr(context.ground_truth, "truth", None) or {}
        expected_labels.extend(normalize_text(label) for label in truth.get("decision_labels") or [])
        predicted_labels.extend(extract_predicted_decision_labels(context))

    expected_set = set(label for label in expected_labels if label)
    predicted_set = set(label for label in predicted_labels if label)

    if not expected_set:
        return not_applicable("missing_expected_decision_labels")

    if not predicted_set:
        return not_applicable("missing_predicted_decision_labels")

    return f1_score(len(expected_set & predicted_set), len(predicted_set), len(expected_set))


def calculate_temporal_consistency(contexts: list[EvaluationTurnContext]) -> MetricCalculation:
    expected = []
    predicted = []

    for context in contexts:
        truth = getattr(context.ground_truth, "truth", None) or {}
        expected.extend(normalize_text(item) for item in truth.get("temporal_assertions") or [])
        predicted.extend(normalize_text(item) for item in get_structured_list(context.output, "temporal_assertions"))

    if not expected:
        return not_applicable("missing_temporal_ground_truth")

    if not predicted:
        return not_applicable("missing_generated_temporal_assertions")

    expected_set = set(expected)
    predicted_set = set(predicted)
    return measured_ratio(len(expected_set & predicted_set), len(expected_set), {"predicted": sorted(predicted_set)})


def calculate_contradiction_handling(contexts: list[EvaluationTurnContext]) -> MetricCalculation:
    expected_count = 0
    detected_count = 0

    for context in contexts:
        truth = getattr(context.ground_truth, "truth", None) or {}
        contradictions = truth.get("contradictions") or []

        if not contradictions:
            continue

        expected_count += len(contradictions)
        output_conflicts = getattr(context.output, "conflicts", None) or get_structured_list(context.output, "conflicts")

        if output_conflicts:
            detected_count += min(len(output_conflicts), len(contradictions))

    if expected_count == 0:
        return not_applicable("no_ground_truth_contradictions")

    return measured_ratio(detected_count, expected_count, {"detected_contradictions": detected_count})


def calculate_correction_recovery(contexts: list[EvaluationTurnContext]) -> MetricCalculation:
    expected = []
    recovered = []

    for context in contexts:
        truth = getattr(context.ground_truth, "truth", None) or {}
        expected.extend(truth.get("correction_expectations") or [])
        recovered.extend(get_structured_list(context.output, "correction_recovered"))

    if not expected:
        return not_applicable("no_correction_cases")

    return measured_ratio(len([item for item in recovered if item is True or item == "true"]), len(expected), {})


def calculate_memory_update_accuracy(contexts: list[EvaluationTurnContext]) -> MetricCalculation:
    expected_labels = []
    predicted_labels = []

    for context in contexts:
        truth = getattr(context.ground_truth, "truth", None) or {}
        expected_labels.extend(normalize_text(item) for item in truth.get("expected_state_transitions") or [])
        predicted_labels.extend(normalize_text(item) for item in get_structured_list(context.output, "state_transitions"))

    if not expected_labels:
        return not_applicable("missing_expected_state_transitions")

    if not predicted_labels:
        return not_applicable("missing_generated_state_transitions")

    expected_set = set(expected_labels)
    predicted_set = set(predicted_labels)
    return f1_score(len(expected_set & predicted_set), len(predicted_set), len(expected_set))


def calculate_state_recovery_time(contexts: list[EvaluationTurnContext]) -> MetricCalculation:
    recovery_turns = []
    expected_recovery = False

    for context in contexts:
        truth = getattr(context.ground_truth, "truth", None) or {}

        if truth.get("recovery_expectations"):
            expected_recovery = True

        for value in get_structured_list(context.output, "state_recovery_turns"):
            try:
                recovery_turns.append(float(value))
            except (TypeError, ValueError):
                continue

    if not expected_recovery:
        return not_applicable("no_recovery_event")

    if not recovery_turns:
        return not_applicable("state_not_recovered")

    recovery_turns.sort()
    median_index = len(recovery_turns) // 2
    median_value = recovery_turns[median_index]
    return measured_value(median_value, {"recovered_samples": len(recovery_turns)}, numerator=median_value)


def extract_predicted_decision_labels(context: EvaluationTurnContext) -> list[str]:
    structured = getattr(context.output, "structured_answer", None) or {}
    labels = structured.get("decision_labels")

    if labels is None:
        labels = structured.get("decision_label") or structured.get("decision") or structured.get("label")

    if labels is None:
        return []

    if isinstance(labels, list):
        return [normalize_text(label) for label in labels]

    return [normalize_text(labels)]


def get_structured_list(output: object, field: str) -> list:
    if output is None:
        return []

    structured = getattr(output, "structured_answer", None) or {}
    value = structured.get(field)

    if value is None:
        return []

    if isinstance(value, list):
        return value

    return [value]
