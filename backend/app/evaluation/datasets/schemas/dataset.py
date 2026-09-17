from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BenchmarkDatasetResponse(BaseModel):
    id: UUID
    name: str
    version: str
    split: str
    description: str
    case_count: int
    checksum: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BenchmarkCaseResponse(BaseModel):
    id: UUID
    dataset_id: UUID
    case_key: str
    scenario_family: str
    seed: int
    manifest: dict
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DatasetDetailResponse(BaseModel):
    dataset: BenchmarkDatasetResponse
    cases: list[BenchmarkCaseResponse]
    validation: dict


class DatasetValidationResponse(BaseModel):
    valid: bool
    dataset_count: int
    case_count: int
    issues: list[str]
