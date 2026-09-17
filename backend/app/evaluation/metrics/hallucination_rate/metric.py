from app.evaluation.common.enums.metrics import MetricDirection
from app.evaluation.metrics.interface.base import MetricDefinition


def definition() -> MetricDefinition:
    return MetricDefinition("hallucination_rate", "Hallucination Rate", "1.0", "Unsupported plus contradicted factual claims divided by factual generated claims.", MetricDirection.LOWER_IS_BETTER, "ratio", ("claim_support_classifications",), "weighted_ratio", "report_missing", "paired_bootstrap")
