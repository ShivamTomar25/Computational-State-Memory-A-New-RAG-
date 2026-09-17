from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.evaluation.experiments.models.experiment import (
    Experiment,
    ExperimentSystemRun,
    ExperimentTurn,
)
from app.evaluation.metrics.models import EvaluationMetricResult
from app.evaluation.statistics.models import StatisticalResult


def create_experiment(db: Session, data: dict) -> Experiment:
    experiment = Experiment(**data)
    db.add(experiment)
    db.flush()
    return experiment


def get_experiment(db: Session, experiment_id: UUID) -> Experiment | None:
    return db.scalar(select(Experiment).where(Experiment.id == experiment_id))


def list_experiments(db: Session, doctor_id: UUID) -> list[Experiment]:
    return list(
        db.scalars(
            select(Experiment)
            .where(Experiment.requested_by_doctor_id == doctor_id)
            .order_by(Experiment.created_at.desc())
        ).all()
    )


def update_experiment(db: Session, experiment: Experiment, data: dict) -> Experiment:
    for field, value in data.items():
        setattr(experiment, field, value)

    db.flush()
    return experiment


def create_system_run(db: Session, data: dict) -> ExperimentSystemRun:
    run = ExperimentSystemRun(**data)
    db.add(run)
    db.flush()
    return run


def list_system_runs(db: Session, experiment_id: UUID) -> list[ExperimentSystemRun]:
    return list(
        db.scalars(
            select(ExperimentSystemRun)
            .where(ExperimentSystemRun.experiment_id == experiment_id)
            .order_by(ExperimentSystemRun.system_type.asc(), ExperimentSystemRun.repetition_number.asc())
        ).all()
    )


def create_turn(db: Session, data: dict) -> ExperimentTurn:
    turn = ExperimentTurn(**data)
    db.add(turn)
    db.flush()
    return turn


def list_turns(db: Session, experiment_id: UUID) -> list[ExperimentTurn]:
    return list(
        db.scalars(
            select(ExperimentTurn)
            .join(ExperimentSystemRun, ExperimentTurn.system_run_id == ExperimentSystemRun.id)
            .where(ExperimentSystemRun.experiment_id == experiment_id)
        ).all()
    )


def create_metric_result(db: Session, data: dict) -> EvaluationMetricResult:
    result = EvaluationMetricResult(**data)
    db.add(result)
    db.flush()
    return result


def list_metric_results(db: Session, experiment_id: UUID) -> list[EvaluationMetricResult]:
    return list(
        db.scalars(
            select(EvaluationMetricResult)
            .where(EvaluationMetricResult.experiment_id == experiment_id)
            .order_by(EvaluationMetricResult.metric_name.asc())
        ).all()
    )


def list_statistical_results(db: Session, experiment_id: UUID) -> list[StatisticalResult]:
    return list(
        db.scalars(
            select(StatisticalResult)
            .where(StatisticalResult.experiment_id == experiment_id)
            .order_by(StatisticalResult.metric_name.asc(), StatisticalResult.system_a.asc(), StatisticalResult.system_b.asc())
        ).all()
    )
