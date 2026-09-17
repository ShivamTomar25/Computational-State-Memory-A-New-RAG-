from app.evaluation.common.enums.metrics import MetricDirection
from app.evaluation.metrics.interface.base import MetricDefinition


def definition() -> MetricDefinition:
    return MetricDefinition("answer_accuracy", "Answer Accuracy", "1.0", "Claim-level macro F1 against accepted ground-truth claims.", MetricDirection.HIGHER_IS_BETTER, "f1", ("generated_claims", "ground_truth_claims"), "macro_f1", "report_missing", "paired_bootstrap")
