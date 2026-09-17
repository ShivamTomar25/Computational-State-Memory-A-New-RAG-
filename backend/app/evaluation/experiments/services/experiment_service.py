from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.doctor.model import Doctor
from app.evaluation.common.enums.metrics import ExperimentStatus
from app.evaluation.datasets.repositories import dataset_repository
from app.evaluation.datasets.services.dataset_service import ensure_default_datasets
from app.evaluation.experiments.repositories import experiment_repository as repository
from app.evaluation.experiments.schemas.experiment import (
    ExperimentCreateRequest,
    ExperimentProgressResponse,
    ExperimentResponse,
    ExperimentResultsResponse,
)
from app.evaluation.experiments.services.live_runner import run_live_experiment
from app.evaluation.experiments.services.metric_evaluation_service import refresh_experiment_metrics
from app.evaluation.exports.services.export_service import list_experiment_exports
from app.evaluation.metrics.registry.registry import list_metric_definitions
from app.evaluation.runners.common.readiness import validate_all_systems_ready


def create_experiment(db: Session, *, doctor: Doctor, request: ExperimentCreateRequest) -> ExperimentResponse:
    ensure_default_datasets(db)
    dataset = dataset_repository.get_dataset(db, request.dataset_id)

    if dataset is None:
        raise ValueError("Dataset not found.")

    profile = request.profile or settings.evaluation_profile
    configuration = {
        "profile": profile,
        "repeats": request.configuration.get("repeats", settings.evaluation_repeats),
        "random_seed": request.configuration.get("random_seed", settings.evaluation_random_seed),
        "max_concurrency": request.configuration.get("max_concurrency", settings.evaluation_max_concurrency),
        "require_all_systems_ready": request.configuration.get(
            "require_all_systems_ready",
            settings.evaluation_require_all_systems_ready,
        ),
        "confirmed_cost": request.confirm_cost,
        **request.configuration,
    }
    experiment = repository.create_experiment(
        db,
        {
            "name": request.name,
            "dataset_id": request.dataset_id,
            "profile": profile,
            "configuration": configuration,
            "status": ExperimentStatus.CREATED.value,
            "comparable": False,
            "requested_by_doctor_id": doctor.id,
        },
    )
    db.commit()
    db.refresh(experiment)
    return ExperimentResponse.model_validate(experiment)


def list_experiments(db: Session, *, doctor: Doctor) -> list[ExperimentResponse]:
    return [ExperimentResponse.model_validate(experiment) for experiment in repository.list_experiments(db, doctor.id)]


def get_experiment(db: Session, *, doctor: Doctor, experiment_id: UUID) -> ExperimentResponse:
    experiment = get_owned_experiment(db, doctor=doctor, experiment_id=experiment_id)
    return ExperimentResponse.model_validate(experiment)


def start_experiment(db: Session, *, doctor: Doctor, experiment_id: UUID) -> ExperimentResponse:
    experiment = get_owned_experiment(db, doctor=doctor, experiment_id=experiment_id)

    if experiment.status not in {
        ExperimentStatus.CREATED.value,
        ExperimentStatus.INCOMPLETE.value,
        ExperimentStatus.FAILED.value,
        "partially_failed",
    }:
        return ExperimentResponse.model_validate(experiment)

    readiness = validate_all_systems_ready()
    experiment = run_live_experiment(db, doctor=doctor, experiment=experiment, readiness=readiness)
    db.refresh(experiment)
    return ExperimentResponse.model_validate(experiment)


def cancel_experiment(db: Session, *, doctor: Doctor, experiment_id: UUID) -> ExperimentResponse:
    experiment = get_owned_experiment(db, doctor=doctor, experiment_id=experiment_id)
    repository.update_experiment(
        db,
        experiment,
        {
            "status": ExperimentStatus.CANCELLED.value,
            "cancelled_at": utc_now(),
            "comparable": False,
        },
    )
    db.commit()
    db.refresh(experiment)
    return ExperimentResponse.model_validate(experiment)


def resume_experiment(db: Session, *, doctor: Doctor, experiment_id: UUID) -> ExperimentResponse:
    return start_experiment(db=db, doctor=doctor, experiment_id=experiment_id)


def get_progress(db: Session, *, doctor: Doctor, experiment_id: UUID) -> ExperimentProgressResponse:
    experiment = get_owned_experiment(db, doctor=doctor, experiment_id=experiment_id)
    refresh_experiment_metrics(db, experiment.id)
    system_runs = repository.list_system_runs(db, experiment.id)
    turns = repository.list_turns(db, experiment.id)
    metric_results = repository.list_metric_results(db, experiment.id)

    return ExperimentProgressResponse(
        experiment_id=experiment.id,
        status=experiment.status,
        expected_system_runs=len(system_runs),
        completed_system_runs=sum(1 for run in system_runs if run.status == "completed"),
        failed_system_runs=sum(1 for run in system_runs if run.status == "failed"),
        expected_turns=len(turns),
        completed_turns=sum(1 for turn in turns if turn.status == "completed"),
        measured_metric_results=sum(
            1
            for result in metric_results
            if (result.details or {}).get("status") in {"measured", "not_applicable"}
        ),
        pending_metric_results=sum(
            1
            for result in metric_results
            if (result.details or {}).get("status") == "pending"
        ),
    )


def get_results(db: Session, *, doctor: Doctor, experiment_id: UUID) -> ExperimentResultsResponse:
    experiment = get_owned_experiment(db, doctor=doctor, experiment_id=experiment_id)
    refresh_experiment_metrics(db, experiment.id)
    metric_results = repository.list_metric_results(db, experiment.id)
    statistics = repository.list_statistical_results(db, experiment.id)

    return ExperimentResultsResponse(
        experiment=ExperimentResponse.model_validate(experiment),
        metric_results=[serialize_metric_result(result) for result in metric_results],
        rankings=build_rankings(metric_results),
        statistics=[serialize_statistic(result) for result in statistics],
        exports=list_experiment_exports(db, experiment_id=experiment.id),
    )


def get_owned_experiment(db: Session, *, doctor: Doctor, experiment_id: UUID):
    experiment = repository.get_experiment(db, experiment_id)

    if experiment is None or experiment.requested_by_doctor_id != doctor.id:
        raise ValueError("Experiment not found.")

    return experiment


def serialize_metric_result(result) -> dict:
    return {
        "id": str(result.id),
        "experiment_id": str(result.experiment_id),
        "system_run_id": str(result.system_run_id) if result.system_run_id else None,
        "turn_id": str(result.turn_id) if result.turn_id else None,
        "metric_name": result.metric_name,
        "metric_version": result.metric_version,
        "value": result.value,
        "numerator": result.numerator,
        "denominator": result.denominator,
        "applicable": result.applicable,
        "reason_not_applicable": result.reason_not_applicable,
        "details": result.details,
    }


def serialize_statistic(result) -> dict:
    return {
        "metric_name": result.metric_name,
        "system_a": result.system_a,
        "system_b": result.system_b,
        "sample_count": result.sample_count,
        "test_name": result.test_name,
        "statistic": result.statistic,
        "raw_p_value": result.raw_p_value,
        "corrected_p_value": result.corrected_p_value,
        "effect_size": result.effect_size,
        "confidence_interval": result.confidence_interval,
        "details": result.details,
    }


def build_rankings(metric_results: list) -> dict:
    rankings = {}

    for metric in list_metric_definitions():
        measured = [result for result in metric_results if result.metric_name == metric.metric_id and result.value is not None]

        if not measured:
            rankings[metric.metric_id] = {
                "status": "not_measured",
                "rows": [],
            }
            continue

        reverse = metric.direction.value == "higher_is_better"
        measured.sort(key=lambda result: result.value, reverse=reverse)
        rankings[metric.metric_id] = {
            "status": "measured",
            "rows": [
                {
                    "rank": index + 1,
                    "system_run_id": str(result.system_run_id) if result.system_run_id else None,
                    "score": result.value,
                    "direction": metric.direction.value,
                }
                for index, result in enumerate(measured)
            ],
        }

    return rankings


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
