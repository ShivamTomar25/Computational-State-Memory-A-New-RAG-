from app.evaluation.common.enums.metrics import MetricDirection
from app.evaluation.metrics.interface.base import MetricDefinition


def definition() -> MetricDefinition:
    return MetricDefinition("correction_recovery", "Correction Recovery", "1.0", "Correct use of corrected facts after explicit correction events.", MetricDirection.HIGHER_IS_BETTER, "ratio", ("correction_truth", "post_correction_answers"), "success_rate", "not_applicable_without_correction", "paired_bootstrap")
