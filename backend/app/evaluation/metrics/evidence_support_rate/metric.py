from app.evaluation.common.enums.metrics import MetricDirection
from app.evaluation.metrics.interface.base import MetricDefinition


def definition() -> MetricDefinition:
    return MetricDefinition("evidence_support_rate", "Evidence Support Rate", "1.0", "Factual claims supported by valid available evidence.", MetricDirection.HIGHER_IS_BETTER, "ratio", ("claim_support_classifications", "citation_audit"), "weighted_ratio", "report_missing", "paired_bootstrap")
