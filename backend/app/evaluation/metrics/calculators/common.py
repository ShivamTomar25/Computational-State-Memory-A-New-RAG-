from __future__ import annotations

from typing import Optional

from app.evaluation.metrics.interface.base import MetricCalculation


def measured_ratio(numerator: float, denominator: float, details: dict) -> MetricCalculation:
    if denominator == 0:
        return not_applicable("zero_denominator", details)

    return MetricCalculation(
        value=numerator / denominator,
        numerator=numerator,
        denominator=denominator,
        applicable=True,
        reason_not_applicable=None,
        details=details,
    )


def measured_value(value: float, details: dict, numerator: Optional[float] = None, denominator: Optional[float] = None) -> MetricCalculation:
    return MetricCalculation(
        value=value,
        numerator=numerator,
        denominator=denominator,
        applicable=True,
        reason_not_applicable=None,
        details=details,
    )


def not_applicable(reason: str, details: Optional[dict] = None) -> MetricCalculation:
    return MetricCalculation(
        value=None,
        numerator=None,
        denominator=None,
        applicable=False,
        reason_not_applicable=reason,
        details=details or {},
    )


def f1_score(true_positive: float, predicted_count: float, truth_count: float) -> MetricCalculation:
    if predicted_count == 0 and truth_count == 0:
        return not_applicable("no_predicted_or_expected_items")

    precision = true_positive / predicted_count if predicted_count else 0.0
    recall = true_positive / truth_count if truth_count else 0.0
    value = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)

    return measured_value(
        value,
        {
            "true_positive": true_positive,
            "predicted_count": predicted_count,
            "truth_count": truth_count,
            "precision": precision,
            "recall": recall,
        },
        numerator=true_positive,
        denominator=truth_count,
    )


def percentile(values: list[float], percentile_value: float) -> Optional[float]:
    if not values:
        return None

    sorted_values = sorted(values)
    index = (len(sorted_values) - 1) * percentile_value
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = index - lower
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * fraction
