from __future__ import annotations

from app.evaluation.metrics.calculators.claim_metrics import calculate_claim_metric_group
from app.evaluation.metrics.calculators.context import EvaluationTurnContext
from app.evaluation.metrics.calculators.efficiency_metrics import calculate_efficiency_metric_group
from app.evaluation.metrics.calculators.retrieval_metrics import calculate_retrieval_metric_group
from app.evaluation.metrics.calculators.state_metrics import calculate_state_metric_group
from app.evaluation.metrics.interface.base import MetricCalculation
from app.evaluation.metrics.registry.registry import list_metric_definitions


def calculate_run_metrics(contexts: list[EvaluationTurnContext]) -> dict[str, MetricCalculation]:
    calculated = {}
    calculated.update(calculate_claim_metric_group(contexts))
    calculated.update(calculate_retrieval_metric_group(contexts))
    calculated.update(calculate_efficiency_metric_group(contexts))
    calculated.update(calculate_state_metric_group(contexts))

    return {
        metric.metric_id: calculated[metric.metric_id]
        for metric in list_metric_definitions()
        if metric.metric_id in calculated
    }
