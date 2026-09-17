from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.evaluation.common.enums.metrics import MetricDirection


@dataclass(frozen=True)
class MetricDefinition:
    metric_id: str
    display_name: str
    version: str
    description: str
    direction: MetricDirection
    unit: str
    required_inputs: tuple[str, ...]
    aggregation_method: str
    missing_value_policy: str
    confidence_interval_method: str


@dataclass(frozen=True)
class MetricCalculation:
    value: Optional[float]
    numerator: Optional[float]
    denominator: Optional[float]
    applicable: bool
    reason_not_applicable: Optional[str]
    details: dict
