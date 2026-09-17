from app.evaluation.common.enums.metrics import MetricDirection
from app.evaluation.metrics.interface.base import MetricDefinition


def definition() -> MetricDefinition:
    return MetricDefinition("temporal_consistency", "Temporal Consistency", "1.0", "Consistency with event order, valid time, and cross-turn history.", MetricDirection.HIGHER_IS_BETTER, "ratio", ("generated_claims", "timeline_events"), "macro_mean", "report_missing", "paired_bootstrap")
