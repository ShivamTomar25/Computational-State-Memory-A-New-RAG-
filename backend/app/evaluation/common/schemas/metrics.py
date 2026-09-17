from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class MetricDefinitionResponse(BaseModel):
    metric_id: str
    display_name: str
    version: str
    description: str
    direction: str
    unit: str
    required_inputs: list[str]
    aggregation_method: str
    missing_value_policy: str
    confidence_interval_method: str


class MetricResultResponse(BaseModel):
    id: UUID
    experiment_id: UUID
    system_run_id: Optional[UUID]
    turn_id: Optional[UUID]
    metric_name: str
    metric_version: str
    value: Optional[float]
    numerator: Optional[float]
    denominator: Optional[float]
    applicable: bool
    reason_not_applicable: Optional[str]
    details: dict

    model_config = ConfigDict(from_attributes=True)
