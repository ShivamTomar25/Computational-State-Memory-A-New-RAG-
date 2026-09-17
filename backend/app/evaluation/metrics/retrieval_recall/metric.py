from app.evaluation.common.enums.metrics import MetricDirection
from app.evaluation.metrics.interface.base import MetricDefinition


def definition() -> MetricDefinition:
    return MetricDefinition("retrieval_recall", "Retrieval Recall", "1.0", "Relevant retrieved context items divided by all expected relevant items.", MetricDirection.HIGHER_IS_BETTER, "recall", ("retrieval_items", "expected_relevant_sources"), "macro_recall_at_k", "report_missing", "paired_bootstrap")
