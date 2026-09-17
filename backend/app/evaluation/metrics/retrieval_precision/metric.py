from app.evaluation.common.enums.metrics import MetricDirection
from app.evaluation.metrics.interface.base import MetricDefinition


def definition() -> MetricDefinition:
    return MetricDefinition("retrieval_precision", "Retrieval Precision", "1.0", "Relevant retrieved context items divided by retrieved items at configured K.", MetricDirection.HIGHER_IS_BETTER, "precision", ("retrieval_items", "expected_relevant_sources"), "macro_precision_at_k", "report_missing", "paired_bootstrap")
