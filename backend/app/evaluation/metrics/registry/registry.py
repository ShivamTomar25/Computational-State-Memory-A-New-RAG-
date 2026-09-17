from __future__ import annotations

from app.evaluation.metrics.answer_accuracy.metric import definition as answer_accuracy
from app.evaluation.metrics.calibration.metric import definition as calibration
from app.evaluation.metrics.contradiction_handling.metric import definition as contradiction_handling
from app.evaluation.metrics.correction_recovery.metric import definition as correction_recovery
from app.evaluation.metrics.cost.metric import definition as cost
from app.evaluation.metrics.decision_f1.metric import definition as decision_f1
from app.evaluation.metrics.evidence_support_rate.metric import definition as evidence_support_rate
from app.evaluation.metrics.fabricated_citation_rate.metric import definition as fabricated_citation_rate
from app.evaluation.metrics.faithfulness.metric import definition as faithfulness
from app.evaluation.metrics.groundedness.metric import definition as groundedness
from app.evaluation.metrics.hallucination_rate.metric import definition as hallucination_rate
from app.evaluation.metrics.latency.metric import definition as latency
from app.evaluation.metrics.lineage_citation_f1.metric import definition as lineage_citation_f1
from app.evaluation.metrics.memory_update_accuracy.metric import definition as memory_update_accuracy
from app.evaluation.metrics.retrieval_precision.metric import definition as retrieval_precision
from app.evaluation.metrics.retrieval_recall.metric import definition as retrieval_recall
from app.evaluation.metrics.state_accuracy.metric import definition as state_accuracy
from app.evaluation.metrics.state_recovery_time.metric import definition as state_recovery_time
from app.evaluation.metrics.temporal_consistency.metric import definition as temporal_consistency
from app.evaluation.metrics.token_usage.metric import definition as token_usage
from app.evaluation.metrics.unsupported_claim_rate.metric import definition as unsupported_claim_rate


METRIC_DEFINITIONS = [
    state_accuracy(),
    temporal_consistency(),
    decision_f1(),
    answer_accuracy(),
    hallucination_rate(),
    evidence_support_rate(),
    unsupported_claim_rate(),
    fabricated_citation_rate(),
    faithfulness(),
    groundedness(),
    calibration(),
    lineage_citation_f1(),
    contradiction_handling(),
    correction_recovery(),
    retrieval_precision(),
    retrieval_recall(),
    token_usage(),
    latency(),
    cost(),
    memory_update_accuracy(),
    state_recovery_time(),
]


def list_metric_definitions():
    return METRIC_DEFINITIONS


def get_metric_definition(metric_id: str):
    for definition in METRIC_DEFINITIONS:
        if definition.metric_id == metric_id:
            return definition

    raise KeyError(metric_id)
