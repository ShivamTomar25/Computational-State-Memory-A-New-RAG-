from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from app.database import SessionLocal, init_db
from app.doctor.model import Doctor
from app.evaluation.datasets.models.dataset import BenchmarkCase
from app.evaluation.experiments.models.experiment import ExperimentOutput, ExperimentSystemRun, ExperimentTurn
from app.evaluation.experiments.repositories import experiment_repository
from app.evaluation.experiments.services.experiment_service import get_progress
from app.evaluation.experiments.services.live_runner import write_statistics
from app.evaluation.experiments.services.metric_evaluation_service import refresh_experiment_metrics
from app.evaluation.scripts.run_sustha_three_patient_pilot import write_export_bundle
from app.memory_systems.common.enums.status import SYSTEM_TYPES
from app.memory_systems.csm.models import CsmActivationItem, CsmActivationRun, CsmStateDependency, CsmStateEvidenceLink, CsmStateVariable


CSM_V2_COMPARISON_SYSTEM_TYPES = tuple(system for system in SYSTEM_TYPES if system not in {"csm_v3", "csm_v4"})


BASE_METRICS = [
    "state_accuracy",
    "temporal_consistency",
    "decision_f1",
    "answer_accuracy",
    "hallucination_rate",
    "evidence_support_rate",
    "unsupported_claim_rate",
    "fabricated_citation_rate",
    "faithfulness",
    "groundedness",
    "expected_calibration_error",
    "lineage_citation_f1",
    "contradiction_handling",
    "correction_recovery",
    "retrieval_precision",
    "retrieval_recall",
    "tokens_per_query",
    "p95_latency",
    "total_cost",
    "memory_update_accuracy",
    "state_recovery_time",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Export the final seven-system CSM v2 derived comparison.")
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--source-experiment-id", required=True)
    parser.add_argument("--patient", required=True)
    parser.add_argument("--repetition", type=int, required=True)
    parser.add_argument("--implementation-version", default="csm_v2")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    init_db()
    db = SessionLocal()
    try:
        experiment = experiment_repository.get_experiment(db, UUID(args.experiment_id))
        if experiment is None:
            raise SystemExit(f"Experiment not found: {args.experiment_id}")
        source = experiment_repository.get_experiment(db, UUID(args.source_experiment_id))
        if source is None:
            raise SystemExit(f"Source experiment not found: {args.source_experiment_id}")
        doctor = db.get(Doctor, experiment.requested_by_doctor_id)
        if doctor is None:
            raise SystemExit("Experiment doctor not found.")
        case = db.scalar(
            select(BenchmarkCase).where(
                BenchmarkCase.dataset_id == experiment.dataset_id,
                BenchmarkCase.case_key == args.patient,
            )
        )
        if case is None:
            raise SystemExit(f"Benchmark case not found: {args.patient}")

        validation_rows = validate_final_scope(
            db,
            experiment_id=experiment.id,
            source_experiment_id=source.id,
            case_id=case.id,
            repetition=args.repetition,
            implementation_version=args.implementation_version,
        )
        critical_failures = [row for row in validation_rows if row["severity"] == "critical" and row["status"] != "passed"]
        if critical_failures:
            write_csv(output_dir / "csm_v2_run_audit.csv", validation_rows)
            write_json(
                output_dir / "csm_v2_run_audit.json",
                {
                    "status": "failed",
                    "critical_failures": critical_failures,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            raise SystemExit("Final CSM v2 validation failed; see csm_v2_run_audit.csv")

        refresh_experiment_metrics(db, experiment.id)
        write_statistics(db, experiment.id)
        progress = get_progress(db, doctor=doctor, experiment_id=experiment.id)
        configuration = {
            **(experiment.configuration or {}),
            "systems": list(CSM_V2_COMPARISON_SYSTEM_TYPES),
            "patients": [args.patient],
            "repetition_filter": [str(args.repetition)],
            "implementation_version": args.implementation_version,
            "derived_from_experiment_id": str(source.id),
        }
        exports = write_export_bundle(
            db,
            experiment_id=experiment.id,
            output_dir=output_dir,
            configuration=configuration,
            import_result={
                "status": "not_run",
                "reason": "derived_comparison_reuses_frozen_baseline_and_existing_dataset_import",
            },
            progress=progress.model_dump(mode="json"),
        )
        matrix_rows = read_csv(output_dir / "system_metric_matrix.csv")
        write_csv(output_dir / "paper_complete_21_metric_matrix.csv", paper_matrix(matrix_rows, BASE_METRICS))
        write_csv(output_dir / "csm_v2_run_audit.csv", validation_rows)
        write_json(
            output_dir / "csm_v2_run_audit.json",
            {
                "status": "passed",
                "experiment_id": str(experiment.id),
                "source_experiment_id": str(source.id),
                "patient": args.patient,
                "repetition": args.repetition,
                "implementation_version": args.implementation_version,
                "validation": validation_rows,
                "exports": exports,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        write_csv(output_dir / "csm_dependency_trace_audit.csv", dependency_trace_rows(db, experiment_id=experiment.id))
        write_csv(output_dir / "csm_activation_component_audit.csv", activation_component_rows(db, experiment_id=experiment.id))

        result = {
            "status": "exported",
            "experiment_id": str(experiment.id),
            "output_dir": str(output_dir),
            "system_metric_matrix": str(output_dir / "system_metric_matrix.csv"),
            "metric_rankings": str(output_dir / "metric_rankings.csv"),
            "paper_complete_21_metric_matrix": str(output_dir / "paper_complete_21_metric_matrix.csv"),
        }
        print(json.dumps(result, indent=2, default=str))
        return 0
    finally:
        db.close()


def validate_final_scope(
    db,
    *,
    experiment_id,
    source_experiment_id,
    case_id,
    repetition: int,
    implementation_version: str,
) -> list[dict]:
    rows = []
    baseline_turns = 0
    csm_turns = 0
    csm_outputs = 0

    for system in CSM_V2_COMPARISON_SYSTEM_TYPES:
        run = db.scalar(
            select(ExperimentSystemRun).where(
                ExperimentSystemRun.experiment_id == experiment_id,
                ExperimentSystemRun.case_id == case_id,
                ExperimentSystemRun.system_type == system,
                ExperimentSystemRun.repetition_number == repetition,
            )
        )
        if run is None:
            rows.append(audit_row("scope", f"{system}_run_exists", "failed", "critical", "missing_run"))
            continue

        turns = list(db.scalars(select(ExperimentTurn).where(ExperimentTurn.system_run_id == run.id)).all())
        outputs = list(
            db.scalars(
                select(ExperimentOutput)
                .join(ExperimentTurn, ExperimentOutput.turn_id == ExperimentTurn.id)
                .where(ExperimentTurn.system_run_id == run.id)
            ).all()
        )

        if system == "csm":
            csm_turns += len(turns)
            csm_outputs += len(outputs)
            run_version = (run.configuration_snapshot or {}).get("implementation_version")
            rows.append(
                audit_row(
                    "scope",
                    "csm_v2_completed_20_turns",
                    "passed" if run.status == "completed" and len(turns) == 20 and len(outputs) == 20 else "failed",
                    "critical",
                    f"status={run.status}; turns={len(turns)}; outputs={len(outputs)}",
                )
            )
            rows.append(
                audit_row(
                    "scope",
                    "csm_implementation_version_recorded",
                    "passed" if run_version == implementation_version else "failed",
                    "critical",
                    f"run_implementation_version={run_version}",
                )
            )
        else:
            frozen = bool((run.configuration_snapshot or {}).get("frozen_baseline"))
            source_id = (run.configuration_snapshot or {}).get("source_experiment_id")
            baseline_turns += len(turns)
            rows.append(
                audit_row(
                    "baseline",
                    f"{system}_frozen_source_reused",
                    "passed" if run.status == "completed" and frozen and source_id == str(source_experiment_id) and len(turns) == 20 and len(outputs) == 20 else "failed",
                    "critical",
                    f"status={run.status}; frozen={frozen}; source_experiment_id={source_id}; turns={len(turns)}; outputs={len(outputs)}",
                )
            )

    rows.append(
        audit_row(
            "baseline",
            "frozen_baseline_total_120_turns",
            "passed" if baseline_turns == 120 else "failed",
            "critical",
            f"baseline_turns={baseline_turns}",
        )
    )
    rows.append(
        audit_row(
            "scope",
            "final_total_140_turns",
            "passed" if baseline_turns + csm_turns == 140 and csm_outputs == 20 else "failed",
            "critical",
            f"baseline_turns={baseline_turns}; csm_turns={csm_turns}; csm_outputs={csm_outputs}",
        )
    )
    return rows


def dependency_trace_rows(db, *, experiment_id) -> list[dict]:
    csm_runs = [
        run
        for run in experiment_repository.list_system_runs(db, experiment_id)
        if run.system_type == "csm" and run.system_instance_id is not None
    ]
    instance_ids = {run.system_instance_id for run in csm_runs}
    if not instance_ids:
        return [{"audit_status": "no_csm_instance_for_experiment"}]
    rows = []
    for dependency in db.scalars(select(CsmStateDependency).where(CsmStateDependency.system_instance_id.in_(instance_ids))).all():
        rows.append(
            {
                "dependency_id": str(dependency.id),
                "system_instance_id": str(dependency.system_instance_id),
                "source_state_id": str(dependency.source_state_id),
                "target_state_id": str(dependency.target_state_id),
                "relation_type": dependency.relation_type,
                "weight": dependency.weight,
                "decay": dependency.decay,
                "status": dependency.status,
            }
        )
    return rows or [{"audit_status": "no_dependencies_materialized"}]


def activation_component_rows(db, *, experiment_id) -> list[dict]:
    csm_runs = [
        run
        for run in experiment_repository.list_system_runs(db, experiment_id)
        if run.system_type == "csm" and run.system_instance_id is not None
    ]
    instance_ids = {run.system_instance_id for run in csm_runs}
    if not instance_ids:
        return [{"audit_status": "no_csm_instance_for_experiment"}]
    rows = []
    activation_runs = list(
        db.scalars(select(CsmActivationRun).where(CsmActivationRun.system_instance_id.in_(instance_ids))).all()
    )
    for activation in activation_runs:
        items = list(
            db.scalars(select(CsmActivationItem).where(CsmActivationItem.activation_run_id == activation.id)).all()
        )
        for item in items:
            state = db.get(CsmStateVariable, item.state_variable_id)
            evidence_link = db.scalar(
                select(CsmStateEvidenceLink).where(CsmStateEvidenceLink.state_variable_id == item.state_variable_id).limit(1)
            )
            rows.append(
                {
                    "activation_run_id": str(activation.id),
                    "query_text": activation.query_text,
                    "state_id": str(item.state_variable_id),
                    "state_key": state.state_key if state else None,
                    "rank": item.rank,
                    "relevance_score": item.relevance_score,
                    "dependency_score": item.dependency_score,
                    "confidence_score": item.confidence_score,
                    "utility_score": item.utility_score,
                    "estimated_token_cost": item.estimated_token_cost,
                    "selected": item.selected,
                    "selection_reason": item.selection_reason,
                    "evidence_id": str(evidence_link.evidence_id) if evidence_link else None,
                }
            )
    return rows or [{"audit_status": "no_activation_items_materialized"}]


def paper_matrix(matrix_rows: list[dict], metrics: list[str]) -> list[dict]:
    by_key = {(row["system"], row["metric_name"]): row for row in matrix_rows}
    rows = []
    for metric in metrics:
        row = {"metric_name": metric}
        for system in CSM_V2_COMPARISON_SYSTEM_TYPES:
            cell = by_key.get((system, metric), {})
            row[system] = cell.get("mean") or cell.get("value")
            row[f"{system}_n"] = cell.get("n") or cell.get("observation_count")
        rows.append(row)
    return rows


def audit_row(category: str, check: str, status: str, severity: str, detail: str) -> dict:
    return {
        "category": category,
        "check": check,
        "status": status,
        "severity": severity,
        "detail": detail,
    }


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True, default=str), encoding="utf-8")


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=sorted({key for row in rows for key in row}))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    raise SystemExit(main())
