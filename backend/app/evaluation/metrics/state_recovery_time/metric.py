from app.evaluation.common.enums.metrics import MetricDirection
from app.evaluation.metrics.interface.base import MetricDefinition


def definition() -> MetricDefinition:
    return MetricDefinition("state_recovery_time", "State Recovery Time", "1.0", "Median turns to first fully correct answer after recovery-triggering events.", MetricDirection.LOWER_IS_BETTER, "turns", ("recovery_events", "answers"), "median_with_censoring", "not_applicable_without_recovery_event", "paired_bootstrap")
