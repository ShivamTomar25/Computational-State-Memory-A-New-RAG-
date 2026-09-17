from app.evaluation.common.enums.metrics import MetricDirection
from app.evaluation.metrics.interface.base import MetricDefinition


def definition() -> MetricDefinition:
    return MetricDefinition("contradiction_handling", "Contradiction Handling", "1.0", "Detection, source identification, state selection, and conflict communication.", MetricDirection.HIGHER_IS_BETTER, "score", ("contradiction_truth", "generated_answer"), "component_mean", "not_applicable_without_contradiction", "paired_bootstrap")
