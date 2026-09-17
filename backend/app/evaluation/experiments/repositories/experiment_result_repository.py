from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.evaluation.datasets.models.dataset import BenchmarkCase, BenchmarkQuestion
from app.evaluation.experiments.models.experiment import (
    Experiment,
    ExperimentClaim,
    ExperimentOutput,
    ExperimentSystemRun,
    ExperimentTurn,
)
from app.evaluation.ground_truth.models.ground_truth import BenchmarkGroundTruth
from app.evaluation.metrics.models import EvaluationMetricResult
from app.llm.common.models.llm import LlmCall
from app.memory_systems.common.models.memory import MemoryRetrievalItem


def list_turns_with_questions(db: Session, experiment_id: UUID):
    return list(
        db.execute(
            select(ExperimentTurn, BenchmarkQuestion)
            .join(ExperimentSystemRun, ExperimentTurn.system_run_id == ExperimentSystemRun.id)
            .join(BenchmarkQuestion, ExperimentTurn.question_id == BenchmarkQuestion.id)
            .where(ExperimentSystemRun.experiment_id == experiment_id)
            .order_by(ExperimentSystemRun.system_type.asc(), ExperimentTurn.turn_number.asc())
        ).all()
    )


def list_outputs(db: Session, experiment_id: UUID) -> list[ExperimentOutput]:
    return list(
        db.scalars(
            select(ExperimentOutput)
            .join(ExperimentTurn, ExperimentOutput.turn_id == ExperimentTurn.id)
            .join(ExperimentSystemRun, ExperimentTurn.system_run_id == ExperimentSystemRun.id)
            .where(ExperimentSystemRun.experiment_id == experiment_id)
        ).all()
    )


def list_claims(db: Session, experiment_id: UUID) -> list[ExperimentClaim]:
    return list(
        db.scalars(
            select(ExperimentClaim)
            .join(ExperimentOutput, ExperimentClaim.output_id == ExperimentOutput.id)
            .join(ExperimentTurn, ExperimentOutput.turn_id == ExperimentTurn.id)
            .join(ExperimentSystemRun, ExperimentTurn.system_run_id == ExperimentSystemRun.id)
            .where(ExperimentSystemRun.experiment_id == experiment_id)
            .order_by(ExperimentClaim.created_at.asc())
        ).all()
    )


def list_ground_truth(db: Session, experiment_id: UUID) -> list[BenchmarkGroundTruth]:
    return list(
        db.scalars(
            select(BenchmarkGroundTruth)
            .join(BenchmarkQuestion, BenchmarkGroundTruth.question_id == BenchmarkQuestion.id)
            .join(BenchmarkCase, BenchmarkQuestion.case_id == BenchmarkCase.id)
            .join(Experiment, BenchmarkCase.dataset_id == Experiment.dataset_id)
            .where(Experiment.id == experiment_id)
        ).all()
    )


def list_retrieval_items(db: Session, experiment_id: UUID) -> list[tuple[UUID, MemoryRetrievalItem]]:
    return list(
        db.execute(
            select(ExperimentTurn.id, MemoryRetrievalItem)
            .select_from(ExperimentTurn)
            .join(MemoryRetrievalItem, MemoryRetrievalItem.retrieval_run_id == ExperimentTurn.retrieval_run_id)
            .join(ExperimentSystemRun, ExperimentTurn.system_run_id == ExperimentSystemRun.id)
            .where(ExperimentSystemRun.experiment_id == experiment_id)
            .order_by(MemoryRetrievalItem.rank.asc())
        ).all()
    )


def list_llm_calls(db: Session, experiment_id: UUID) -> list[tuple[UUID, LlmCall]]:
    return list(
        db.execute(
            select(ExperimentTurn.id, LlmCall)
            .select_from(ExperimentTurn)
            .join(LlmCall, LlmCall.id == ExperimentTurn.llm_call_id)
            .join(ExperimentSystemRun, ExperimentTurn.system_run_id == ExperimentSystemRun.id)
            .where(ExperimentSystemRun.experiment_id == experiment_id)
        ).all()
    )


def get_metric_result(
    db: Session,
    *,
    experiment_id: UUID,
    system_run_id: UUID,
    metric_name: str,
) -> Optional[EvaluationMetricResult]:
    return db.scalar(
        select(EvaluationMetricResult).where(
            EvaluationMetricResult.experiment_id == experiment_id,
            EvaluationMetricResult.system_run_id == system_run_id,
            EvaluationMetricResult.metric_name == metric_name,
            EvaluationMetricResult.turn_id.is_(None),
        )
    )


def save_metric_result(db: Session, result: EvaluationMetricResult, data: dict) -> EvaluationMetricResult:
    for field, value in data.items():
        setattr(result, field, value)

    db.flush()
    return result
