from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ExperimentCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    dataset_id: UUID
    profile: str = "smoke"
    configuration: dict = Field(default_factory=dict)
    confirm_cost: bool = False


class ExperimentResponse(BaseModel):
    id: UUID
    name: str
    dataset_id: UUID
    profile: str
    configuration: dict
    status: str
    comparable: bool
    requested_by_doctor_id: UUID
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    cancelled_at: Optional[datetime]
    failure_reason: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class ExperimentProgressResponse(BaseModel):
    experiment_id: UUID
    status: str
    expected_system_runs: int
    completed_system_runs: int
    failed_system_runs: int
    expected_turns: int
    completed_turns: int
    measured_metric_results: int
    pending_metric_results: int


class ExperimentResultsResponse(BaseModel):
    experiment: ExperimentResponse
    metric_results: list[dict]
    rankings: dict
    statistics: list[dict]
    exports: list[dict]
