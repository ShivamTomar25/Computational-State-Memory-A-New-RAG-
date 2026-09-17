from app.evaluation.common.enums.metrics import MetricDirection
from app.evaluation.metrics.interface.base import MetricDefinition


def definition() -> MetricDefinition:
    return MetricDefinition("fabricated_citation_rate", "Fabricated Citation Rate", "1.0", "Generated citations that cannot resolve to supplied valid evidence.", MetricDirection.LOWER_IS_BETTER, "ratio", ("citations", "retrieval_context"), "weighted_ratio", "report_missing", "paired_bootstrap")
