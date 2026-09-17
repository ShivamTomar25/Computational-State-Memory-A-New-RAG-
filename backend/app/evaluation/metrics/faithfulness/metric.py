from app.evaluation.common.enums.metrics import MetricDirection
from app.evaluation.metrics.interface.base import MetricDefinition


def definition() -> MetricDefinition:
    return MetricDefinition("faithfulness", "Faithfulness", "1.0", "Factual claims supported by the context supplied to the final-answer model.", MetricDirection.HIGHER_IS_BETTER, "ratio", ("generated_claims", "retrieval_context"), "weighted_ratio", "report_missing", "paired_bootstrap")
