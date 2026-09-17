from app.evaluation.common.enums.metrics import MetricDirection
from app.evaluation.metrics.interface.base import MetricDefinition


def definition() -> MetricDefinition:
    return MetricDefinition("tokens_per_query", "Tokens per Query", "1.0", "Online answer input plus output tokens per completed query.", MetricDirection.LOWER_IS_BETTER, "tokens", ("llm_calls",), "mean", "report_missing", "paired_bootstrap")
