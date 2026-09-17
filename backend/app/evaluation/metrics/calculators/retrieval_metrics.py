from __future__ import annotations

from app.evaluation.metrics.calculators.claim_metrics import get_expected_source_ids
from app.evaluation.metrics.calculators.common import measured_ratio, not_applicable
from app.evaluation.metrics.calculators.context import EvaluationTurnContext
from app.evaluation.metrics.interface.base import MetricCalculation


def calculate_retrieval_metric_group(contexts: list[EvaluationTurnContext]) -> dict[str, MetricCalculation]:
    expected_ids = get_expected_source_ids(contexts)
    retrieved_ids = get_retrieved_source_ids(contexts)

    if not retrieved_ids:
        return {
            "retrieval_precision": not_applicable("no_retrieved_context_items"),
            "retrieval_recall": not_applicable("no_retrieved_context_items"),
        }

    if not expected_ids:
        return {
            "retrieval_precision": not_applicable("missing_expected_relevant_sources"),
            "retrieval_recall": not_applicable("missing_expected_relevant_sources"),
        }

    relevant_retrieved = retrieved_ids & expected_ids
    details = {
        "retrieved_source_ids": sorted(retrieved_ids),
        "expected_source_ids": sorted(expected_ids),
        "relevant_retrieved_ids": sorted(relevant_retrieved),
    }

    return {
        "retrieval_precision": measured_ratio(len(relevant_retrieved), len(retrieved_ids), details),
        "retrieval_recall": measured_ratio(len(relevant_retrieved), len(expected_ids), details),
    }


def get_retrieved_source_ids(contexts: list[EvaluationTurnContext]) -> set[str]:
    retrieved_ids = set()

    for context in contexts:
        for item in context.retrieval_items:
            canonical_source_id = getattr(item, "canonical_source_id", None)
            document_id = getattr(item, "document_id", None)
            section_id = getattr(item, "section_id", None)

            for value in (canonical_source_id, document_id, section_id):
                if value is not None:
                    retrieved_ids.add(str(value))

    return retrieved_ids
