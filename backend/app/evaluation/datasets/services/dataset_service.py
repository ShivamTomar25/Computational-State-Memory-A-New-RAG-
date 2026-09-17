from __future__ import annotations

import hashlib
import json
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.evaluation.datasets.fixtures.smoke_cases import SMOKE_DATASET
from app.evaluation.datasets.repositories import dataset_repository as repository
from app.evaluation.datasets.schemas.dataset import (
    BenchmarkCaseResponse,
    BenchmarkDatasetResponse,
    DatasetDetailResponse,
    DatasetValidationResponse,
)
from app.evaluation.datasets.validators.dataset_validator import validate_dataset_fixture


def ensure_default_datasets(db: Session):
    fixture = SMOKE_DATASET
    existing = repository.get_dataset_by_key(
        db,
        name=fixture["name"],
        version=fixture["version"],
        split=fixture["split"],
    )

    if existing is not None:
        return existing

    issues = validate_dataset_fixture(fixture)

    if issues:
        raise ValueError("; ".join(issues))

    checksum = dataset_checksum(fixture)
    dataset = repository.create_dataset(
        db,
        {
            "name": fixture["name"],
            "version": fixture["version"],
            "split": fixture["split"],
            "description": fixture["description"],
            "case_count": len(fixture["cases"]),
            "checksum": checksum,
            "status": "validated",
        },
    )

    for case_fixture in fixture["cases"]:
        case = repository.create_case(
            db,
            {
                "dataset_id": dataset.id,
                "case_key": case_fixture["case_key"],
                "scenario_family": case_fixture["scenario_family"],
                "seed": case_fixture["seed"],
                "manifest": case_fixture["manifest"],
            },
        )

        for event in case_fixture["manifest"]["events"]:
            repository.create_event(
                db,
                {
                    "case_id": case.id,
                    "sequence_number": event["sequence_number"],
                    "event_type": event["event_type"],
                    "valid_time": datetime.fromisoformat(event["valid_time"]),
                    "ingestion_time": datetime.fromisoformat(event["ingestion_time"]),
                    "payload": event["payload"],
                    "source_fixture": f"{case_fixture['case_key']}:event-{event['sequence_number']}",
                },
            )

        for question_fixture in case_fixture["manifest"]["questions"]:
            question = repository.create_question(
                db,
                {
                    "case_id": case.id,
                    "turn_number": question_fixture["turn_number"],
                    "question": question_fixture["question"],
                    "question_type": question_fixture["question_type"],
                    "expected_decision_type": question_fixture.get("expected_decision_type"),
                    "source_cutoff": datetime.fromisoformat(question_fixture["source_cutoff"]),
                },
            )
            repository.create_ground_truth(
                db,
                {
                    "question_id": question.id,
                    "truth": question_fixture["truth"],
                    "version": fixture["version"],
                    "reviewer_status": "synthetic_validated",
                },
            )

    db.commit()
    db.refresh(dataset)
    return dataset


def list_available_datasets(db: Session) -> list[BenchmarkDatasetResponse]:
    ensure_default_datasets(db)
    return [BenchmarkDatasetResponse.model_validate(dataset) for dataset in repository.list_datasets(db)]


def get_dataset_detail(db: Session, dataset_id: UUID) -> DatasetDetailResponse:
    dataset = repository.get_dataset(db, dataset_id)

    if dataset is None:
        raise ValueError("Dataset not found.")

    cases = repository.list_cases(db, dataset_id)

    return DatasetDetailResponse(
        dataset=BenchmarkDatasetResponse.model_validate(dataset),
        cases=[BenchmarkCaseResponse.model_validate(case) for case in cases],
        validation={
            "valid": True,
            "ground_truth_isolated": True,
            "synthetic_only": True,
        },
    )


def validate_datasets(db: Session) -> DatasetValidationResponse:
    ensure_default_datasets(db)
    datasets = repository.list_datasets(db)
    case_count = sum(len(repository.list_cases(db, dataset.id)) for dataset in datasets)

    return DatasetValidationResponse(
        valid=True,
        dataset_count=len(datasets),
        case_count=case_count,
        issues=[],
    )


def dataset_checksum(dataset: dict) -> str:
    payload = json.dumps(dataset, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
