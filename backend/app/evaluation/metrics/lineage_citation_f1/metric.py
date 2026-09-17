from app.evaluation.common.enums.metrics import MetricDirection
from app.evaluation.metrics.interface.base import MetricDefinition


def definition() -> MetricDefinition:
    return MetricDefinition("lineage_citation_f1", "Lineage/Citation F1", "1.0", "F1 over canonical source, document, page, and section references.", MetricDirection.HIGHER_IS_BETTER, "f1", ("citations", "expected_evidence"), "macro_f1", "report_missing", "paired_bootstrap")
