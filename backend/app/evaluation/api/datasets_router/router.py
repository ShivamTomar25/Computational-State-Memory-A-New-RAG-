from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.doctor.dependencies import CurrentDoctor
from app.evaluation.common.schemas.metrics import MetricDefinitionResponse
from app.evaluation.datasets.schemas.dataset import (
    BenchmarkDatasetResponse,
    DatasetDetailResponse,
    DatasetValidationResponse,
)
from app.evaluation.datasets.services.dataset_service import (
    get_dataset_detail,
    list_available_datasets,
    validate_datasets,
)
from app.evaluation.metrics.registry.registry import list_metric_definitions


router = APIRouter()
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("/api/evaluation/metrics", response_model=list[MetricDefinitionResponse])
def get_evaluation_metrics(current_doctor: CurrentDoctor) -> list[MetricDefinitionResponse]:
    return [
        MetricDefinitionResponse(
            metric_id=metric.metric_id,
            display_name=metric.display_name,
            version=metric.version,
            description=metric.description,
            direction=metric.direction.value,
            unit=metric.unit,
            required_inputs=list(metric.required_inputs),
            aggregation_method=metric.aggregation_method,
            missing_value_policy=metric.missing_value_policy,
            confidence_interval_method=metric.confidence_interval_method,
        )
        for metric in list_metric_definitions()
    ]


@router.get("/api/evaluation/datasets", response_model=list[BenchmarkDatasetResponse])
def get_evaluation_datasets(current_doctor: CurrentDoctor, db: DatabaseSession) -> list[BenchmarkDatasetResponse]:
    return list_available_datasets(db)


@router.get("/api/evaluation/datasets/{dataset_id}", response_model=DatasetDetailResponse)
def get_evaluation_dataset(dataset_id: UUID, current_doctor: CurrentDoctor, db: DatabaseSession) -> DatasetDetailResponse:
    try:
        return get_dataset_detail(db, dataset_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post("/api/evaluation/datasets/validate", response_model=DatasetValidationResponse)
def validate_evaluation_datasets(current_doctor: CurrentDoctor, db: DatabaseSession) -> DatasetValidationResponse:
    return validate_datasets(db)
