from app.evaluation.common.enums.metrics import MetricDirection
from app.evaluation.metrics.interface.base import MetricDefinition


def definition() -> MetricDefinition:
    return MetricDefinition("total_cost", "Total Cost", "1.0", "Versioned provider-token cost for operational system calls.", MetricDirection.LOWER_IS_BETTER, "usd", ("token_usage", "model_pricing"), "sum", "unavailable_when_pricing_missing", "paired_bootstrap")
