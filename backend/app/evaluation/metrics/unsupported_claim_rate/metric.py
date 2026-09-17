from app.evaluation.common.enums.metrics import MetricDirection
from app.evaluation.metrics.interface.base import MetricDefinition


def definition() -> MetricDefinition:
    return MetricDefinition("unsupported_claim_rate", "Unsupported Claim Rate", "1.0", "Unsupported factual claims divided by claims requiring evidence.", MetricDirection.LOWER_IS_BETTER, "ratio", ("claim_support_classifications",), "weighted_ratio", "report_missing", "paired_bootstrap")
