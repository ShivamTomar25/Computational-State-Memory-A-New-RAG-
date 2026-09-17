from __future__ import annotations

import argparse
import csv
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from app.database import SessionLocal, init_db
from app.evaluation.datasets.models.dataset import BenchmarkCase, BenchmarkQuestion
from app.evaluation.experiments.models.experiment import (
    Experiment,
    ExperimentClaim,
    ExperimentOutput,
    ExperimentSystemRun,
    ExperimentTurn,
)
from app.evaluation.experiments.repositories import experiment_repository
from app.evaluation.metrics.models import EvaluationMetricResult
from app.evaluation.metrics.registry.registry import list_metric_definitions
from app.memory_systems.common.enums.status import SYSTEM_TYPES


CSM_V2_COMPARISON_SYSTEM_TYPES = tuple(system for system in SYSTEM_TYPES if system not in {"csm_v3", "csm_v4"})


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a CSM v2 derived experiment with frozen non-CSM baseline turns.")
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
        source = experiment_repository.get_experiment(db, UUID(args.source_experiment_id))
        if source is None:
            raise SystemExit(f"Source experiment not found: {args.source_experiment_id}")

        case = db.scalar(
            select(BenchmarkCase).where(
                BenchmarkCase.dataset_id == source.dataset_id,
                BenchmarkCase.case_key == args.patient,
            )
        )
        if case is None:
            raise SystemExit(f"Benchmark case not found for patient: {args.patient}")

        questions = list(
            db.scalars(
                select(BenchmarkQuestion)
                .where(BenchmarkQuestion.case_id == case.id)
                .order_by(BenchmarkQuestion.turn_number.asc())
            ).all()
        )
        if not questions:
            raise SystemExit(f"No benchmark questions found for patient: {args.patient}")

        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        configuration = {
            "repeats": 1,
            "temperature": (source.configuration or {}).get("temperature", 0),
            "require_all_systems_ready": False,
            "independent_turns": True,
            "systems": list(CSM_V2_COMPARISON_SYSTEM_TYPES),
            "patients": [args.patient],
            "questions": [],
            "repetition_filter": [str(args.repetition)],
            "top_k": (source.configuration or {}).get("top_k"),
            "token_budget": (source.configuration or {}).get("token_budget"),
            "max_concurrency": 1,
            "request_delay_seconds": (source.configuration or {}).get("request_delay_seconds", 3),
            "max_retries": (source.configuration or {}).get("max_retries", 8),
            "llm_provider": (source.configuration or {}).get("llm_provider"),
            "llm_model": (source.configuration or {}).get("llm_model"),
            "max_output_tokens": (source.configuration or {}).get("max_output_tokens"),
            "pricing_version": (source.configuration or {}).get("pricing_version"),
            "skip_sync": False,
            "implementation_version": args.implementation_version,
            "derived_from_experiment_id": str(source.id),
            "frozen_baseline_systems": [system for system in CSM_V2_COMPARISON_SYSTEM_TYPES if system != "csm"],
            "baseline_reuse_policy": "copy_completed_non_csm_turn_records_without_provider_rerun",
        }
        derived = Experiment(
            name=f"CSM v2 derived comparison {args.patient} rep{args.repetition} {run_id}",
            dataset_id=source.dataset_id,
            profile=source.profile,
            configuration=configuration,
            status="incomplete",
            comparable=False,
            requested_by_doctor_id=source.requested_by_doctor_id,
        )
        db.add(derived)
        db.flush()

        baseline_rows = []
        copied_turns = 0
        copied_outputs = 0
        frozen_systems = [system for system in CSM_V2_COMPARISON_SYSTEM_TYPES if system != "csm"]

        for system_type in frozen_systems:
            source_run = db.scalar(
                select(ExperimentSystemRun).where(
                    ExperimentSystemRun.experiment_id == source.id,
                    ExperimentSystemRun.case_id == case.id,
                    ExperimentSystemRun.system_type == system_type,
                    ExperimentSystemRun.repetition_number == args.repetition,
                )
            )
            if source_run is None:
                raise SystemExit(f"Missing source baseline run: {system_type}")
            if source_run.status != "completed":
                raise SystemExit(f"Source baseline run is not completed: {system_type} status={source_run.status}")

            derived_run = ExperimentSystemRun(
                experiment_id=derived.id,
                case_id=case.id,
                system_type=system_type,
                repetition_number=args.repetition,
                system_instance_id=source_run.system_instance_id,
                conversation_id=source_run.conversation_id,
                status="completed",
                source_cutoff=source_run.source_cutoff,
                source_snapshot_hash=source_run.source_snapshot_hash,
                configuration_snapshot={
                    **deepcopy(source_run.configuration_snapshot or {}),
                    "frozen_baseline": True,
                    "source_experiment_id": str(source.id),
                    "source_system_run_id": str(source_run.id),
                },
                started_at=source_run.started_at,
                completed_at=source_run.completed_at,
                failure_reason=None,
            )
            db.add(derived_run)
            db.flush()

            source_turns = list(
                db.scalars(
                    select(ExperimentTurn)
                    .where(ExperimentTurn.system_run_id == source_run.id)
                    .order_by(ExperimentTurn.turn_number.asc())
                ).all()
            )
            if len(source_turns) != len(questions):
                raise SystemExit(f"Expected {len(questions)} source turns for {system_type}, found {len(source_turns)}")

            for source_turn in source_turns:
                if source_turn.status != "completed":
                    raise SystemExit(f"Source turn is not completed: {system_type} turn={source_turn.turn_number}")

                derived_turn = ExperimentTurn(
                    system_run_id=derived_run.id,
                    question_id=source_turn.question_id,
                    turn_number=source_turn.turn_number,
                    user_message_id=source_turn.user_message_id,
                    assistant_message_id=source_turn.assistant_message_id,
                    retrieval_run_id=source_turn.retrieval_run_id,
                    llm_call_id=source_turn.llm_call_id,
                    status="completed",
                    started_at=source_turn.started_at,
                    completed_at=source_turn.completed_at,
                )
                db.add(derived_turn)
                db.flush()
                copied_turns += 1

                source_output = db.scalar(select(ExperimentOutput).where(ExperimentOutput.turn_id == source_turn.id))
                if source_output is None:
                    raise SystemExit(f"Missing source output: {system_type} turn={source_turn.turn_number}")
                derived_output = ExperimentOutput(
                    turn_id=derived_turn.id,
                    answer_text=source_output.answer_text,
                    structured_answer=deepcopy(source_output.structured_answer or {}),
                    answer_confidence=source_output.answer_confidence,
                    insufficient_evidence=source_output.insufficient_evidence,
                    citations=deepcopy(source_output.citations or []),
                    conflicts=deepcopy(source_output.conflicts or []),
                )
                db.add(derived_output)
                db.flush()
                copied_outputs += 1

                claims = list(
                    db.scalars(
                        select(ExperimentClaim)
                        .where(ExperimentClaim.output_id == source_output.id)
                        .order_by(ExperimentClaim.created_at.asc())
                    ).all()
                )
                for claim in claims:
                    db.add(
                        ExperimentClaim(
                            output_id=derived_output.id,
                            claim_id=claim.claim_id,
                            claim_text=claim.claim_text,
                            normalized_claim=deepcopy(claim.normalized_claim or {}),
                            confidence=claim.confidence,
                            citation_ids=deepcopy(claim.citation_ids or []),
                            source_support_status=claim.source_support_status,
                        )
                    )

            copy_metric_rows(db, source_experiment_id=source.id, source_run=source_run, derived_experiment_id=derived.id, derived_run=derived_run)
            baseline_rows.append(
                {
                    "system": system_type,
                    "source_system_run_id": str(source_run.id),
                    "derived_system_run_id": str(derived_run.id),
                    "turns_copied": len(source_turns),
                    "status": "frozen_completed",
                }
            )

        csm_run = ExperimentSystemRun(
            experiment_id=derived.id,
            case_id=case.id,
            system_type="csm",
            repetition_number=args.repetition,
            system_instance_id=None,
            conversation_id=None,
            status="pending",
            source_cutoff=None,
            source_snapshot_hash=None,
            configuration_snapshot={
                "profile": source.profile,
                "system_type": "csm",
                "implementation_version": args.implementation_version,
                "frozen_baseline": False,
                "source_experiment_id": str(source.id),
            },
        )
        db.add(csm_run)
        db.flush()
        create_metric_placeholders(db, experiment_id=derived.id, system_run=csm_run)
        db.commit()

        audit = {
            "status": "prepared",
            "source_experiment_id": str(source.id),
            "derived_experiment_id": str(derived.id),
            "patient": args.patient,
            "repetition": args.repetition,
            "baseline_system_count": len(frozen_systems),
            "baseline_turn_count": copied_turns,
            "baseline_output_count": copied_outputs,
            "csm_turns_to_generate": len(questions),
            "implementation_version": args.implementation_version,
            "baseline_systems": baseline_rows,
        }
        write_json(output_dir / "derived_experiment_manifest.json", audit)
        write_json(output_dir / "baseline_reuse_audit.json", audit)
        write_csv(output_dir / "baseline_reuse_audit.csv", baseline_rows)
        print(json.dumps(audit, indent=2, default=str))
        return 0
    finally:
        db.close()


def copy_metric_rows(
    db,
    *,
    source_experiment_id,
    source_run: ExperimentSystemRun,
    derived_experiment_id,
    derived_run: ExperimentSystemRun,
) -> None:
    rows = list(
        db.scalars(
            select(EvaluationMetricResult).where(
                EvaluationMetricResult.experiment_id == source_experiment_id,
                EvaluationMetricResult.system_run_id == source_run.id,
                EvaluationMetricResult.turn_id.is_(None),
            )
        ).all()
    )

    if rows:
        for row in rows:
            details = deepcopy(row.details or {})
            details["frozen_baseline"] = True
            details["source_experiment_id"] = str(source_experiment_id)
            details["source_system_run_id"] = str(source_run.id)
            db.add(
                EvaluationMetricResult(
                    experiment_id=derived_experiment_id,
                    system_run_id=derived_run.id,
                    turn_id=None,
                    metric_name=row.metric_name,
                    metric_version=row.metric_version,
                    value=row.value,
                    numerator=row.numerator,
                    denominator=row.denominator,
                    applicable=row.applicable,
                    reason_not_applicable=row.reason_not_applicable,
                    details=details,
                )
            )
        return

    create_metric_placeholders(db, experiment_id=derived_experiment_id, system_run=derived_run)


def create_metric_placeholders(db, *, experiment_id, system_run: ExperimentSystemRun) -> None:
    for metric in list_metric_definitions():
        db.add(
            EvaluationMetricResult(
                experiment_id=experiment_id,
                system_run_id=system_run.id,
                turn_id=None,
                metric_name=metric.metric_id,
                metric_version=metric.version,
                value=None,
                numerator=None,
                denominator=None,
                applicable=False,
                reason_not_applicable="pending_live_evaluation_run",
                details={
                    "status": "pending",
                    "system_type": system_run.system_type,
                    "case_id": str(system_run.case_id),
                    "repetition_number": system_run.repetition_number,
                },
            )
        )


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
