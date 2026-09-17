from app.evaluation.common.enums.metrics import MetricDirection
from app.evaluation.metrics.interface.base import MetricDefinition


def definition() -> MetricDefinition:
    return MetricDefinition("memory_update_accuracy", "Memory Update Accuracy", "1.0", "Macro F1 over expected state transition labels after updates.", MetricDirection.HIGHER_IS_BETTER, "f1", ("state_transitions", "generated_claims"), "macro_f1", "report_missing", "paired_bootstrap")
