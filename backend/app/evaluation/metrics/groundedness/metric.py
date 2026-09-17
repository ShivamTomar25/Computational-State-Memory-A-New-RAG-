from app.evaluation.common.enums.metrics import MetricDirection
from app.evaluation.metrics.interface.base import MetricDefinition


def definition() -> MetricDefinition:
    return MetricDefinition("groundedness", "Groundedness", "1.0", "Evidence relevance, entailment, valid time, and resolvable lineage.", MetricDirection.HIGHER_IS_BETTER, "score", ("generated_claims", "citations", "source_lineage"), "weighted_mean", "report_missing", "paired_bootstrap")
