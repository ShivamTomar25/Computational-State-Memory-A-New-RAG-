from app.evaluation.common.enums.metrics import MetricDirection
from app.evaluation.metrics.interface.base import MetricDefinition


def definition() -> MetricDefinition:
    return MetricDefinition("expected_calibration_error", "Expected Calibration Error", "1.0", "Confidence calibration error using real answer or claim confidence values.", MetricDirection.LOWER_IS_BETTER, "ece", ("confidence", "claim_correctness"), "bin_weighted_error", "not_applicable_when_missing_confidence", "paired_bootstrap")
