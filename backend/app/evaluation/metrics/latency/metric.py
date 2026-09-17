from app.evaluation.common.enums.metrics import MetricDirection
from app.evaluation.metrics.interface.base import MetricDefinition


def definition() -> MetricDefinition:
    return MetricDefinition("p95_latency", "p95 Latency", "1.0", "95th percentile end-to-end backend query latency.", MetricDirection.LOWER_IS_BETTER, "milliseconds", ("turn_timings",), "p95", "report_missing", "paired_bootstrap")
