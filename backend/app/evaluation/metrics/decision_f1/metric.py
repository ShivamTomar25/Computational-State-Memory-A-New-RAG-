from app.evaluation.common.enums.metrics import MetricDirection
from app.evaluation.metrics.interface.base import MetricDefinition


def definition() -> MetricDefinition:
    return MetricDefinition("decision_f1", "Decision F1", "1.0", "Macro F1 over controlled research decision labels.", MetricDirection.HIGHER_IS_BETTER, "f1", ("predicted_labels", "ground_truth_labels"), "macro_f1", "report_missing", "paired_bootstrap")
