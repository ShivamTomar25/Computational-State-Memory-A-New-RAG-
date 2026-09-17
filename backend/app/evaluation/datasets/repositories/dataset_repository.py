from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.evaluation.datasets.models.dataset import (
    BenchmarkCase,
    BenchmarkDataset,
    BenchmarkEvent,
    BenchmarkQuestion,
)
from app.evaluation.ground_truth.models.ground_truth import BenchmarkGroundTruth


def list_datasets(db: Session) -> list[BenchmarkDataset]:
    return list(db.scalars(select(BenchmarkDataset).order_by(BenchmarkDataset.created_at.desc())).all())


def get_dataset(db: Session, dataset_id: UUID) -> BenchmarkDataset | None:
    return db.scalar(select(BenchmarkDataset).where(BenchmarkDataset.id == dataset_id))


def get_dataset_by_key(db: Session, *, name: str, version: str, split: str) -> BenchmarkDataset | None:
    return db.scalar(
        select(BenchmarkDataset).where(
            BenchmarkDataset.name == name,
            BenchmarkDataset.version == version,
            BenchmarkDataset.split == split,
        )
    )


def list_cases(db: Session, dataset_id: UUID) -> list[BenchmarkCase]:
    return list(
        db.scalars(
            select(BenchmarkCase)
            .where(BenchmarkCase.dataset_id == dataset_id)
            .order_by(BenchmarkCase.case_key.asc())
        ).all()
    )


def list_questions_for_case(db: Session, case_id: UUID) -> list[BenchmarkQuestion]:
    return list(
        db.scalars(
            select(BenchmarkQuestion)
            .where(BenchmarkQuestion.case_id == case_id)
            .order_by(BenchmarkQuestion.turn_number.asc())
        ).all()
    )


def create_dataset(db: Session, data: dict) -> BenchmarkDataset:
    dataset = BenchmarkDataset(**data)
    db.add(dataset)
    db.flush()
    return dataset


def create_case(db: Session, data: dict) -> BenchmarkCase:
    case = BenchmarkCase(**data)
    db.add(case)
    db.flush()
    return case


def create_event(db: Session, data: dict) -> BenchmarkEvent:
    event = BenchmarkEvent(**data)
    db.add(event)
    db.flush()
    return event


def create_question(db: Session, data: dict) -> BenchmarkQuestion:
    question = BenchmarkQuestion(**data)
    db.add(question)
    db.flush()
    return question


def create_ground_truth(db: Session, data: dict) -> BenchmarkGroundTruth:
    truth = BenchmarkGroundTruth(**data)
    db.add(truth)
    db.flush()
    return truth
