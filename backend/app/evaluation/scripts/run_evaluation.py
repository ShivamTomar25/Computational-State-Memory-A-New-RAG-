from __future__ import annotations

import argparse
import json

from sqlalchemy import select

from app.database import SessionLocal, init_db
from app.doctor.model import Doctor
from app.evaluation.datasets.services.dataset_service import ensure_default_datasets, validate_datasets
from app.evaluation.experiments.repositories import experiment_repository
from app.evaluation.experiments.schemas.experiment import ExperimentCreateRequest
from app.evaluation.experiments.services.experiment_service import create_experiment, get_progress, start_experiment
from app.evaluation.metrics.registry.registry import list_metric_definitions
from app.evaluation.runners.common.readiness import validate_all_systems_ready
from app.memory_systems.common.enums.status import SYSTEM_TYPES


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="smoke", choices=["smoke", "pilot", "full", "ablation", "robustness"])
    parser.add_argument("--confirm-cost", action="store_true")
    parser.add_argument("--execute-live", action="store_true")
    parser.add_argument("--doctor-email")
    parser.add_argument("--repeats", type=int, default=1)
    args = parser.parse_args()

    if (args.profile == "full" or args.execute_live) and not args.confirm_cost:
        print(json.dumps({"status": "blocked", "reason": "full_profile_requires_confirm_cost"}, indent=2))
        return 1

    init_db()
    db = SessionLocal()

    try:
        dataset = ensure_default_datasets(db)
        validation = validate_datasets(db)
        readiness = validate_all_systems_ready()

        if args.execute_live:
            doctor = select_doctor(db, email=args.doctor_email)
            experiment = create_experiment(
                db,
                doctor=doctor,
                request=ExperimentCreateRequest(
                    name=f"Live {args.profile} evaluation",
                    dataset_id=dataset.id,
                    profile=args.profile,
                    configuration={
                        "repeats": args.repeats,
                        "require_all_systems_ready": False,
                    },
                    confirm_cost=True,
                ),
            )
            started = start_experiment(db, doctor=doctor, experiment_id=experiment.id)
            progress = get_progress(db, doctor=doctor, experiment_id=experiment.id)
            runs = experiment_repository.list_system_runs(db, experiment.id)
            turns = experiment_repository.list_turns(db, experiment.id)
            metrics = experiment_repository.list_metric_results(db, experiment.id)
            statistics = experiment_repository.list_statistical_results(db, experiment.id)
            result = {
                "status": started.status,
                "experiment_id": str(experiment.id),
                "failure_reason": started.failure_reason,
                "profile": args.profile,
                "dataset_id": str(dataset.id),
                "doctor_email": doctor.email,
                "systems": sorted({run.system_type for run in runs}),
                "expected_systems": len(SYSTEM_TYPES),
                "system_run_count": len(runs),
                "turn_count": len(turns),
                "registered_metric_count": len(list_metric_definitions()),
                "metric_row_count": len(metrics),
                "metric_status_counts": metric_status_counts(metrics),
                "system_run_status_counts": system_run_status_counts(runs),
                "measured_value_count": sum(1 for metric in metrics if metric.value is not None),
                "pending_metric_count": sum(1 for metric in metrics if (metric.details or {}).get("status") == "pending"),
                "statistical_result_count": len(statistics),
                "progress": progress.model_dump(mode="json"),
                "system_readiness": readiness,
            }
            print(json.dumps(result, indent=2, default=str))
            return 0 if started.status in {"completed", "partially_failed"} else 1

        result = {
            "status": "prepared",
            "profile": args.profile,
            "dataset_id": str(dataset.id),
            "dataset": {
                "name": dataset.name,
                "version": dataset.version,
                "split": dataset.split,
                "case_count": dataset.case_count,
                "checksum": dataset.checksum,
            },
            "validation": validation.model_dump(),
            "metrics": len(list_metric_definitions()),
            "system_readiness": readiness,
            "measured_scores_created": False,
            "reason": "This command validates the evaluation scaffold and does not fabricate measured scores.",
        }
        print(json.dumps(result, indent=2, default=str))
        return 0 if readiness["ready"] else 2
    finally:
        db.close()


def select_doctor(db, *, email: str | None):
    if email:
        doctor = db.scalar(select(Doctor).where(Doctor.email == email))
    else:
        doctor = db.scalar(select(Doctor).order_by(Doctor.created_at.asc()))

    if doctor is None:
        raise ValueError("No doctor account exists. Create a doctor before running live evaluation.")

    return doctor


def metric_status_counts(metrics) -> dict:
    counts = {}

    for metric in metrics:
        status = (metric.details or {}).get("status", "missing")
        counts[status] = counts.get(status, 0) + 1

    return counts


def system_run_status_counts(runs) -> dict:
    counts = {}

    for run in runs:
        counts[run.status] = counts.get(run.status, 0) + 1

    return counts


if __name__ == "__main__":
    raise SystemExit(main())
