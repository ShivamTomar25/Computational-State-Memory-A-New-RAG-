from app.evaluation.common.enums.metrics import MetricDirection
from app.evaluation.metrics.interface.base import MetricDefinition


def definition() -> MetricDefinition:
    return MetricDefinition("state_accuracy", "State Accuracy", "1.0", "Correct current-state components against ground truth.", MetricDirection.HIGHER_IS_BETTER, "ratio", ("generated_claims", "ground_truth_state"), "weighted_mean", "report_missing", "paired_bootstrap")
