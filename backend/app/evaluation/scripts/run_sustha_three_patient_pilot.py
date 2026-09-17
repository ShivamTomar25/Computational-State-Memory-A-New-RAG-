from __future__ import annotations

import argparse
import csv
import json
import math
import shlex
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev
from uuid import UUID

from sqlalchemy import func, select

from app.config import settings
from app.database import SessionLocal, init_db
from app.doctor.model import Doctor
from app.document.models import Document, DocumentText
from app.evaluation.datasets.models.dataset import BenchmarkCase, BenchmarkDataset, BenchmarkQuestion
from app.evaluation.experiments.models.experiment import ExperimentClaim, ExperimentOutput, ExperimentSystemRun, ExperimentTurn
from app.evaluation.experiments.repositories import experiment_repository
from app.evaluation.experiments.repositories import experiment_result_repository
from app.evaluation.experiments.schemas.experiment import ExperimentCreateRequest
from app.evaluation.experiments.services.experiment_service import create_experiment, get_progress, start_experiment
from app.evaluation.experiments.services.live_runner import ProviderRateLimitExceeded, ProviderRetryableTurnError, normalize_question_filter
from app.evaluation.ground_truth.models.ground_truth import BenchmarkGroundTruth
from app.evaluation.metrics.cost.pricing import estimate_token_cost
from app.evaluation.metrics.models import EvaluationMetricResult
from app.evaluation.metrics.registry.registry import list_metric_definitions
from app.evaluation.scripts.import_sustha_pack import DATASET_NAME, DATASET_SPLIT, import_pack
from app.llm.common.models.llm import LlmCall
from app.memory_systems.common.enums.status import SYSTEM_TYPES
from app.memory_systems.common.models.memory import (
    CanonicalMemorySource,
    MemoryIngestionRun,
    MemoryRetrievalItem,
    MemoryRetrievalRun,
    MemorySystemInstance,
)
from app.patient.model import Patient


RESULTS_SUBDIR = Path("evaluation/results/sustha_three_patient_pilot")
PAPER_METRIC_GROUPS = {
    "answer_quality": [
        "answer_accuracy",
        "decision_f1",
        "hallucination_rate",
        "evidence_support_rate",
        "unsupported_claim_rate",
        "faithfulness",
        "groundedness",
        "expected_calibration_error",
    ],
    "retrieval": ["retrieval_precision", "retrieval_recall", "lineage_citation_f1", "fabricated_citation_rate"],
    "state_memory": [
        "state_accuracy",
        "temporal_consistency",
        "contradiction_handling",
        "correction_recovery",
        "memory_update_accuracy",
        "state_recovery_time",
    ],
    "efficiency": ["tokens_per_query", "p95_latency", "total_cost"],
}
MAIN_METRICS = [
    "state_accuracy",
    "temporal_consistency",
    "decision_f1",
    "answer_accuracy",
    "expected_calibration_error",
    "lineage_citation_f1",
    "hallucination_rate",
    "tokens_per_query",
    "p95_latency",
    "total_cost",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", default="../sustha_three_patient_evaluation_pack")
    parser.add_argument("--systems", default="all")
    parser.add_argument("--system", action="append", default=[])
    parser.add_argument("--patient", action="append", default=[])
    parser.add_argument("--question", action="append", default=[])
    parser.add_argument("--repetition", action="append", default=[])
    parser.add_argument("--experiment-id")
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--request-delay-seconds", type=float, default=3)
    parser.add_argument("--max-retries", type=int, default=8)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--temperature", type=float, default=0)
    parser.add_argument("--implementation-version", default=None)
    parser.add_argument("--output-dir")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-import", action="store_true")
    parser.add_argument("--skip-sync", action="store_true")
    parser.add_argument("--export-paper-results", action="store_true")
    parser.add_argument("--confirm-cost", action="store_true")
    args = parser.parse_args()

    if args.resume and args.reset:
        raise ValueError("Do not use --reset while resuming an experiment.")

    if args.experiment_id and args.reset:
        raise ValueError("Do not use --reset with --experiment-id.")

    selected_systems = parse_systems(args)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    pack_path = Path(args.pack).resolve()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else (pack_path.parent / RESULTS_SUBDIR / run_id)

    if args.dry_run:
        print(
            json.dumps(
                {
                    "status": "dry_run",
                    "pack_path": str(pack_path),
                    "output_dir": str(output_dir),
                    "systems": selected_systems,
                    "patients": args.patient or "all",
                    "questions": args.question or "all",
                    "repetition_filter": args.repetition or "all",
                    "repetitions": args.repetitions,
                    "concurrency": args.concurrency,
                    "request_delay_seconds": args.request_delay_seconds,
                    "max_retries": args.max_retries,
                    "implementation_version": args.implementation_version,
                    "estimated_turns": estimate_turns(args, selected_systems),
                    "live_llm_required": True,
                },
                indent=2,
            )
        )
        return 0

    if not args.confirm_cost:
        print(json.dumps({"status": "blocked", "reason": "live_pilot_requires_confirm_cost"}, indent=2))
        return 1

    init_db()
    db = SessionLocal()

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        import_result = None

        if args.resume or args.experiment_id:
            args.skip_import = True

        if not args.skip_import:
            import_result = import_pack(
                db,
                pack_path=pack_path,
                reset=args.reset,
                skip_sync=args.skip_sync,
                output_dir=output_dir,
            )
        elif args.skip_sync:
            write_json(output_dir / "source_ingestion_audit.json", source_ingestion_audit(db))

        dataset = select_dataset(db)
        doctor = select_doctor(db)
        configuration = {
            "repeats": args.repetitions,
            "temperature": args.temperature,
            "require_all_systems_ready": False,
            "independent_turns": True,
            "systems": selected_systems,
            "patients": args.patient,
            "questions": args.question,
            "repetition_filter": args.repetition,
            "top_k": settings.memory_default_top_k,
            "token_budget": settings.memory_default_context_token_budget,
            "max_concurrency": args.concurrency,
            "request_delay_seconds": args.request_delay_seconds,
            "max_retries": args.max_retries,
            "llm_provider": settings.llm_provider,
            "llm_model": settings.groq_model,
            "max_output_tokens": settings.groq_answer_max_tokens,
            "pricing_version": "2026-07-21",
            "skip_sync": args.skip_sync,
            "implementation_version": args.implementation_version,
        }
        experiment = None

        if args.experiment_id:
            experiment = experiment_repository.get_experiment(db, UUID(args.experiment_id))

            if experiment is None:
                raise ValueError(f"Experiment not found: {args.experiment_id}")

            if experiment.requested_by_doctor_id != doctor.id:
                raise ValueError("Experiment does not belong to the synthetic evaluation doctor.")

            merge_resume_configuration(db, experiment, configuration)
        elif args.resume:
            experiment = find_resume_experiment(db, dataset_id=dataset.id, doctor_id=doctor.id, configuration=configuration)

        if experiment is None:
            response = create_experiment(
                db,
                doctor=doctor,
                request=ExperimentCreateRequest(
                    name=f"Sustha three-patient pilot {run_id}",
                    dataset_id=dataset.id,
                    profile="pilot",
                    configuration=configuration,
                    confirm_cost=True,
                ),
            )
            experiment = experiment_repository.get_experiment(db, response.id)

        try:
            print(json.dumps({"resume_command": render_resume_command(args)}, indent=2))
            started = start_experiment(db, doctor=doctor, experiment_id=experiment.id)
        except ProviderRateLimitExceeded as error:
            progress = get_progress(db, doctor=doctor, experiment_id=experiment.id)
            print(
                json.dumps(
                    {
                        "status": "incomplete",
                        "reason": "provider_rate_limited",
                        "experiment_id": str(experiment.id),
                        "run_id": run_id,
                        "output_dir": str(output_dir),
                        "failure_reason": str(error),
                        "progress": progress.model_dump(mode="json"),
                    },
                    indent=2,
                    default=str,
                )
            )
            return 2
        except ProviderRetryableTurnError as error:
            progress = get_progress(db, doctor=doctor, experiment_id=experiment.id)
            print(
                json.dumps(
                    {
                        "status": "incomplete",
                        "reason": "retryable_provider_failure",
                        "experiment_id": str(experiment.id),
                        "run_id": run_id,
                        "output_dir": str(output_dir),
                        "failure_reason": str(error),
                        "progress": progress.model_dump(mode="json"),
                    },
                    indent=2,
                    default=str,
                )
            )
            return 2

        progress = get_progress(db, doctor=doctor, experiment_id=experiment.id)
        export_paths = write_export_bundle(
            db,
            experiment_id=experiment.id,
            output_dir=output_dir,
            configuration=configuration,
            import_result=import_result,
            progress=progress.model_dump(mode="json"),
        )
        result = {
            "status": started.status,
            "experiment_id": str(experiment.id),
            "run_id": run_id,
            "output_dir": str(output_dir),
            "failure_reason": started.failure_reason,
            "progress": progress.model_dump(mode="json"),
            "exports": export_paths,
        }
        print(json.dumps(result, indent=2, default=str))
        return 0 if started.status in {"completed", "partially_failed"} else 1
    finally:
        db.close()


def parse_systems(args) -> list[str]:
    values = []

    if args.system:
        values.extend(args.system)
    elif args.systems and args.systems != "all":
        values.extend(part.strip() for part in args.systems.split(",") if part.strip())
    else:
        return list(SYSTEM_TYPES)

    unknown = sorted(set(values) - set(SYSTEM_TYPES))

    if unknown:
        raise ValueError(f"Unknown memory system(s): {', '.join(unknown)}")

    return values


def estimate_turns(args, systems: list[str]) -> int:
    patient_count = len(args.patient) or 3
    question_count = len(args.question) or 20
    repetition_count = len(args.repetition) or args.repetitions
    return patient_count * question_count * len(systems) * repetition_count


def render_resume_command(args) -> str:
    command = [
        "venv/bin/python",
        "-m",
        "app.evaluation.scripts.run_sustha_three_patient_pilot",
        "--pack",
        args.pack,
        "--experiment-id",
        args.experiment_id or "",
        "--resume",
    ]
    for patient in args.patient:
        command.extend(["--patient", patient])
    for repetition in args.repetition:
        command.extend(["--repetition", str(repetition)])
    if args.systems:
        command.extend(["--systems", args.systems])
    for system in args.system:
        command.extend(["--system", system])
    for question in args.question:
        command.extend(["--question", str(question)])
    if args.implementation_version:
        command.extend(["--implementation-version", args.implementation_version])
    command.extend(
        [
            "--concurrency",
            str(args.concurrency),
            "--request-delay-seconds",
            str(args.request_delay_seconds),
            "--max-retries",
            str(args.max_retries),
            "--export-paper-results",
            "--confirm-cost",
        ]
    )
    return " ".join(shlex.quote(part) for part in command if part)


def select_dataset(db) -> BenchmarkDataset:
    dataset = db.scalar(
        select(BenchmarkDataset).where(
            BenchmarkDataset.name == DATASET_NAME,
            BenchmarkDataset.split == DATASET_SPLIT,
        )
    )

    if dataset is None:
        raise ValueError("Sustha three-patient dataset is not imported.")

    return dataset


def select_doctor(db) -> Doctor:
    doctor = db.scalar(select(Doctor).where(Doctor.email == "research.doctor@sustha.test"))

    if doctor is None:
        raise ValueError("Synthetic evaluation doctor is not imported.")

    return doctor


def find_resume_experiment(db, *, dataset_id, doctor_id, configuration: dict):
    return db.scalar(
        select(experiment_repository.Experiment)
        .where(
            experiment_repository.Experiment.dataset_id == dataset_id,
            experiment_repository.Experiment.requested_by_doctor_id == doctor_id,
            experiment_repository.Experiment.configuration == configuration,
        )
        .order_by(experiment_repository.Experiment.created_at.desc())
    )


def merge_resume_configuration(db, experiment, configuration: dict) -> None:
    merged = {**(experiment.configuration or {})}

    for key in (
        "patients",
        "questions",
        "repetition_filter",
        "systems",
        "max_concurrency",
        "request_delay_seconds",
        "max_retries",
        "skip_sync",
        "implementation_version",
    ):
        if configuration.get(key) not in (None, [], ""):
            merged[key] = configuration[key]

    experiment.configuration = merged

    if experiment.status == "running":
        experiment.status = "incomplete"
        experiment.failure_reason = "Resuming interrupted experiment."

    reset_interrupted_turns(db, experiment.id, configuration)
    db.commit()


def reset_interrupted_turns(db, experiment_id: UUID, configuration: dict) -> None:
    scope = build_export_scope(db, experiment_id, configuration)
    turns = db.scalars(
        select(ExperimentTurn)
        .join(ExperimentSystemRun, ExperimentTurn.system_run_id == ExperimentSystemRun.id)
        .where(
            ExperimentSystemRun.experiment_id == experiment_id,
            ExperimentTurn.id.in_(scope["turn_ids"] or [None]),
            ExperimentTurn.status.in_(["synchronizing", "retrieving", "generating", "evaluating"]),
        )
    ).all()

    for turn in turns:
        if db.scalar(select(ExperimentOutput.id).where(ExperimentOutput.turn_id == turn.id)) is None:
            turn.status = "pending"
            turn.completed_at = None


def write_export_bundle(db, *, experiment_id: UUID, output_dir: Path, configuration: dict, import_result, progress: dict) -> dict:
    scope = build_export_scope(db, experiment_id, configuration)
    metric_summary = build_metric_summary(db, experiment_id, scope)
    rankings = build_metric_rankings(metric_summary)
    statistics = serialize_statistics(db, experiment_id, scope)
    export_paths = {}

    manifest = build_experiment_manifest(db, experiment_id, import_result=import_result, progress=progress, scope=scope)
    write_json(output_dir / "experiment_manifest.json", manifest)
    write_json(output_dir / "configuration.json", configuration)
    write_json(output_dir / "system_metric_matrix.json", metric_summary)
    write_csv(output_dir / "system_metric_matrix.csv", flatten_metric_summary(metric_summary))
    write_json(output_dir / "metric_rankings.json", rankings)
    write_csv(output_dir / "metric_rankings.csv", flatten_rankings(rankings))
    write_json(output_dir / "statistical_results.json", statistics)
    write_csv(output_dir / "statistical_results.csv", statistics)
    write_csv(output_dir / "per_patient_results.csv", per_patient_results(db, experiment_id, scope))
    write_csv(output_dir / "per_question_results.csv", per_question_results(db, experiment_id, scope))
    write_csv(output_dir / "per_system_results.csv", per_system_results(metric_summary))
    write_csv(output_dir / "per_repetition_results.csv", per_repetition_results(db, experiment_id, scope))
    write_json(output_dir / "system_initialization_audit.json", system_initialization_audit(db))

    if not (output_dir / "source_ingestion_audit.json").exists():
        write_json(output_dir / "source_ingestion_audit.json", source_ingestion_audit(db))

    write_quality_exports(db, experiment_id, output_dir, scope)
    write_efficiency_exports(db, experiment_id, output_dir, scope)
    write_paper_exports(output_dir, metric_summary, rankings, statistics, manifest)

    for path in sorted(output_dir.iterdir()):
        if path.is_file():
            export_paths[path.name] = str(path)

    return export_paths


def build_export_scope(db, experiment_id: UUID, configuration: dict) -> dict:
    selected_patients = set(configuration.get("patients") or [])
    selected_systems = set(configuration.get("systems") or [])
    selected_repetitions = {int(value) for value in configuration.get("repetition_filter") or []}
    selected_questions = normalize_question_filter(configuration.get("questions") or [])
    runs = experiment_repository.list_system_runs(db, experiment_id)
    cases_by_id = {case.id: case for case in db.scalars(select(BenchmarkCase)).all()}
    questions_by_id = {question.id: question for question in db.scalars(select(BenchmarkQuestion)).all()}
    truth_by_question = {
        truth.question_id: truth
        for truth in db.scalars(select(BenchmarkGroundTruth)).all()
    }

    scoped_runs = []
    for run in runs:
        case = cases_by_id.get(run.case_id)
        if case is None:
            continue
        if selected_patients and case.case_key not in selected_patients:
            continue
        if selected_systems and run.system_type not in selected_systems:
            continue
        if selected_repetitions and run.repetition_number not in selected_repetitions:
            continue
        scoped_runs.append(run)

    scoped_run_ids = {run.id for run in scoped_runs}
    turns = []
    for turn in experiment_repository.list_turns(db, experiment_id):
        if turn.system_run_id not in scoped_run_ids:
            continue
        question = questions_by_id.get(turn.question_id)
        if selected_questions and not question_in_scope(question, selected_questions, truth_by_question):
            continue
        turns.append(turn)

    scoped_turn_ids = {turn.id for turn in turns}
    metrics = []
    for result in experiment_repository.list_metric_results(db, experiment_id):
        if result.system_run_id and result.system_run_id in scoped_run_ids:
            if result.turn_id is None or result.turn_id in scoped_turn_ids:
                metrics.append(result)

    return {
        "runs": scoped_runs,
        "run_ids": scoped_run_ids,
        "turns": turns,
        "turn_ids": scoped_turn_ids,
        "metrics": metrics,
        "cases_by_id": cases_by_id,
        "questions_by_id": questions_by_id,
        "filters": {
            "patients": sorted(selected_patients) if selected_patients else "all",
            "systems": sorted(selected_systems) if selected_systems else "all",
            "repetitions": sorted(selected_repetitions) if selected_repetitions else "all",
            "questions": sorted(selected_questions) if selected_questions else "all",
        },
    }


def question_in_scope(question: BenchmarkQuestion | None, selected_questions: set[str], truth_by_question: dict) -> bool:
    if question is None:
        return False
    if str(question.turn_number) in selected_questions or str(question.id) in selected_questions:
        return True
    truth = truth_by_question.get(question.id)
    return truth is not None and str((truth.truth or {}).get("question_id")) in selected_questions


def build_experiment_manifest(db, experiment_id: UUID, *, import_result, progress: dict, scope: dict) -> dict:
    experiment = experiment_repository.get_experiment(db, experiment_id)
    runs = scope["runs"]
    turns = scope["turns"]
    metrics = scope["metrics"]
    docs = int(db.scalar(select(func.count()).select_from(Document)) or 0)
    texts = int(db.scalar(select(func.count()).select_from(DocumentText)) or 0)

    return {
        "experiment_id": str(experiment_id),
        "dataset_id": str(experiment.dataset_id),
        "status": experiment.status,
        "comparable": experiment.comparable,
        "created_at": experiment.created_at.isoformat(),
        "started_at": experiment.started_at.isoformat() if experiment.started_at else None,
        "completed_at": experiment.completed_at.isoformat() if experiment.completed_at else None,
        "failure_reason": experiment.failure_reason,
        "systems": sorted({run.system_type for run in runs}),
        "system_run_count": len(runs),
        "turn_count": len(turns),
        "metric_row_count": len(metrics),
        "measured_metric_rows": sum(1 for metric in metrics if metric.value is not None),
        "pending_metric_rows": sum(1 for metric in metrics if (metric.details or {}).get("status") == "pending"),
        "document_count": docs,
        "document_text_count": texts,
        "progress": progress,
        "export_scope": scope["filters"],
        "import_result": import_result,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def build_metric_summary(db, experiment_id: UUID, scope: dict) -> dict:
    runs_by_id = {run.id: run for run in scope["runs"]}
    definitions = {definition.metric_id: definition for definition in list_metric_definitions()}
    grouped = {system: {metric_id: [] for metric_id in definitions} for system in SYSTEM_TYPES}

    for result in scope["metrics"]:
        run = runs_by_id.get(result.system_run_id)

        if run is None:
            continue

        grouped.setdefault(run.system_type, {}).setdefault(result.metric_name, []).append(result)

    summary = {}

    for system, by_metric in grouped.items():
        summary[system] = {}

        for metric_id, definition in definitions.items():
            rows = by_metric.get(metric_id, [])
            values = [float(row.value) for row in rows if row.value is not None]
            ci = confidence_interval(values)
            summary[system][metric_id] = {
                "metric_name": metric_id,
                "display_name": definition.display_name,
                "direction": definition.direction.value,
                "unit": definition.unit,
                "formula": definition.description,
                "aggregation_level": definition.aggregation_method,
                "applicability_rules": definition.missing_value_policy,
                "version": definition.version,
                "required_inputs": list(definition.required_inputs),
                "mean": mean(values) if values else None,
                "stddev": pstdev(values) if len(values) > 1 else 0 if values else None,
                "ci95_low": ci[0],
                "ci95_high": ci[1],
                "n": len(values),
                "applicable_rows": sum(1 for row in rows if row.applicable),
                "not_applicable_rows": sum(1 for row in rows if not row.applicable),
                "pending_rows": sum(1 for row in rows if (row.details or {}).get("status") == "pending"),
                "failed_rows": sum(1 for row in rows if (row.details or {}).get("status") == "failed"),
                "reason_not_applicable": first_reason(rows),
            }

    return summary


def confidence_interval(values: list[float]) -> tuple[float | None, float | None]:
    if not values:
        return None, None

    if len(values) == 1:
        return values[0], values[0]

    spread = pstdev(values)
    half_width = 1.96 * spread / math.sqrt(len(values))
    center = mean(values)
    return center - half_width, center + half_width


def first_reason(rows) -> str | None:
    for row in rows:
        if row.reason_not_applicable:
            return row.reason_not_applicable
    return None


def build_metric_rankings(metric_summary: dict) -> dict:
    rankings = {}

    for definition in list_metric_definitions():
        metric_rows = []

        for system, metrics in metric_summary.items():
            row = metrics.get(definition.metric_id, {})

            if row.get("mean") is not None:
                metric_rows.append(
                    {
                        "system": system,
                        "score": row["mean"],
                        "ci95_low": row["ci95_low"],
                        "ci95_high": row["ci95_high"],
                        "n": row["n"],
                    }
                )

        reverse = definition.direction.value == "higher_is_better"
        metric_rows.sort(key=lambda item: item["score"], reverse=reverse)

        for index, row in enumerate(metric_rows, start=1):
            row["rank"] = index
            row["direction"] = definition.direction.value
            row["metric_name"] = definition.metric_id
            row["tie_with_top"] = index > 1 and confidence_intervals_overlap(metric_rows[0], row)

        rankings[definition.metric_id] = metric_rows

    return rankings


def confidence_intervals_overlap(first: dict, second: dict) -> bool:
    if first.get("ci95_low") is None or second.get("ci95_low") is None:
        return False

    return max(first["ci95_low"], second["ci95_low"]) <= min(first["ci95_high"], second["ci95_high"])


def serialize_statistics(db, experiment_id: UUID, scope: dict) -> list[dict]:
    runs_by_id = {run.id: run for run in scope["runs"]}
    by_metric = {}

    for result in scope["metrics"]:
        run = runs_by_id.get(result.system_run_id)
        if run is None or result.value is None:
            continue
        by_metric.setdefault(result.metric_name, {}).setdefault(run.system_type, {})[
            (str(run.case_id), run.repetition_number)
        ] = float(result.value)

    rows = []
    for metric_name, system_values in by_metric.items():
        systems = sorted(system_values)
        pair_count = max(1, len(systems) * (len(systems) - 1) // 2)
        for index, system_a in enumerate(systems):
            for system_b in systems[index + 1 :]:
                paired_keys = sorted(set(system_values[system_a]) & set(system_values[system_b]))
                if not paired_keys:
                    continue
                diffs = [system_values[system_a][key] - system_values[system_b][key] for key in paired_keys]
                mean_diff = sum(diffs) / len(diffs)
                variance = sum((value - mean_diff) ** 2 for value in diffs) / (len(diffs) - 1) if len(diffs) > 1 else 0.0
                stddev = math.sqrt(variance)
                stderr = stddev / math.sqrt(len(diffs)) if diffs else 0.0
                z_score = abs(mean_diff / stderr) if stderr else None
                raw_p = math.erfc(z_score / math.sqrt(2)) if z_score is not None else None
                rows.append(
                    {
                        "metric_name": metric_name,
                        "system_a": system_a,
                        "system_b": system_b,
                        "sample_count": len(diffs),
                        "test_name": "scoped_paired_difference_normal_approximation",
                        "statistic": mean_diff,
                        "raw_p_value": raw_p,
                        "corrected_p_value": min(raw_p * pair_count, 1.0) if raw_p is not None else None,
                        "effect_size": mean_diff / stddev if stddev else None,
                        "confidence_interval": {"low": mean_diff - 1.96 * stderr, "high": mean_diff + 1.96 * stderr, "level": 0.95},
                        "details": {"paired_keys": paired_keys, "differences": diffs, "scope": scope["filters"]},
                    }
                )
    return rows


def flatten_metric_summary(summary: dict) -> list[dict]:
    return [
        {"system": system, **row}
        for system, metrics in summary.items()
        for row in metrics.values()
    ]


def flatten_rankings(rankings: dict) -> list[dict]:
    return [row for rows in rankings.values() for row in rows]


def per_patient_results(db, experiment_id: UUID, scope: dict) -> list[dict]:
    rows = []
    runs_by_id = {run.id: run for run in scope["runs"]}
    cases_by_id = scope["cases_by_id"]

    for result in scope["metrics"]:
        run = runs_by_id.get(result.system_run_id)
        case = cases_by_id.get(run.case_id) if run else None

        if run and case:
            rows.append(
                {
                    "patient_code": case.case_key,
                    "system": run.system_type,
                    "repetition": run.repetition_number,
                    "metric_name": result.metric_name,
                    "value": result.value,
                    "applicable": result.applicable,
                    "reason_not_applicable": result.reason_not_applicable,
                }
            )

    return rows


def per_question_results(db, experiment_id: UUID, scope: dict) -> list[dict]:
    rows = []
    runs_by_id = {run.id: run for run in scope["runs"]}
    questions_by_id = scope["questions_by_id"]

    for turn in scope["turns"]:
        run = runs_by_id.get(turn.system_run_id)
        question = questions_by_id.get(turn.question_id)
        output = db.scalar(select(ExperimentOutput).where(ExperimentOutput.turn_id == turn.id))

        rows.append(
            {
                "turn_id": str(turn.id),
                "system": run.system_type if run else None,
                "repetition": run.repetition_number if run else None,
                "turn_number": turn.turn_number,
                "question": question.question if question else None,
                "source_cutoff": question.source_cutoff.isoformat() if question else None,
                "status": turn.status,
                "has_output": output is not None,
                "answer_confidence": output.answer_confidence if output else None,
                "insufficient_evidence": output.insufficient_evidence if output else None,
            }
        )

    return rows


def per_system_results(summary: dict) -> list[dict]:
    rows = []

    for system, metrics in summary.items():
        measured = [row["mean"] for row in metrics.values() if row.get("mean") is not None]
        rows.append(
            {
                "system": system,
                "measured_metric_count": len(measured),
                "mean_across_measured_metrics": mean(measured) if measured else None,
                "pending_metric_count": sum(row["pending_rows"] for row in metrics.values()),
                "not_applicable_metric_count": sum(1 for row in metrics.values() if row.get("mean") is None and row.get("not_applicable_rows")),
            }
        )

    return rows


def per_repetition_results(db, experiment_id: UUID, scope: dict) -> list[dict]:
    rows = []
    runs_by_id = {run.id: run for run in scope["runs"]}

    for result in scope["metrics"]:
        run = runs_by_id.get(result.system_run_id)

        if run:
            rows.append(
                {
                    "system": run.system_type,
                    "repetition": run.repetition_number,
                    "case_id": str(run.case_id),
                    "metric_name": result.metric_name,
                    "value": result.value,
                    "applicable": result.applicable,
                }
            )

    return rows


def system_initialization_audit(db) -> list[dict]:
    latest_runs = list(
        db.execute(
            select(MemorySystemInstance, Patient, MemoryIngestionRun)
            .join(Patient, MemorySystemInstance.patient_id == Patient.id)
            .outerjoin(MemoryIngestionRun, MemoryIngestionRun.system_instance_id == MemorySystemInstance.id)
            .order_by(Patient.patient_code.asc(), MemorySystemInstance.system_type.asc(), MemoryIngestionRun.created_at.desc())
        ).all()
    )
    seen = set()
    rows = []

    for instance, patient, run in latest_runs:
        key = (instance.id, run.id if run else None)

        if key in seen:
            continue

        seen.add(key)
        rows.append(
            {
                "patient_code": patient.patient_code,
                "system_type": instance.system_type,
                "instance_status": instance.status,
                "pipeline_version": instance.pipeline_version,
                "initialized_at": iso(instance.initialized_at),
                "last_synced_at": iso(instance.last_synced_at),
                "capability_status": instance.capability_status,
                "configuration": instance.configuration,
                "ingestion_run_id": str(run.id) if run else None,
                "sync_status": run.status if run else None,
                "source_count": run.source_count if run else None,
                "processed_count": run.processed_count if run else None,
                "failed_count": run.failed_count if run else None,
                "failure_code": run.failure_code if run else instance.failure_code,
                "failure_reason": run.failure_reason if run else instance.failure_reason,
            }
        )

    return rows


def source_ingestion_audit(db) -> dict:
    patients = []

    for patient in db.scalars(select(Patient).order_by(Patient.patient_code.asc())).all():
        sources = list(db.scalars(select(CanonicalMemorySource).where(CanonicalMemorySource.patient_id == patient.id)).all())
        by_type = {}
        by_subtype = {}

        for source in sources:
            by_type[source.source_type] = by_type.get(source.source_type, 0) + 1
            subtype = f"{source.source_type}:{source.source_subtype}"
            by_subtype[subtype] = by_subtype.get(subtype, 0) + 1

        patients.append(
            {
                "patient_code": patient.patient_code,
                "patient_id": str(patient.id),
                "canonical_source_count": len(sources),
                "counts_by_source_type": by_type,
                "counts_by_source_subtype": by_subtype,
                "effective_dates": sorted({iso(source.valid_time) for source in sources if source.valid_time}),
                "ingestion_dates": sorted({iso(source.recorded_time) for source in sources if source.recorded_time}),
            }
        )

    return {
        "patients": patients,
        "totals": {
            "canonical_sources": int(db.scalar(select(func.count()).select_from(CanonicalMemorySource)) or 0),
            "documents": int(db.scalar(select(func.count()).select_from(Document)) or 0),
            "document_texts": int(db.scalar(select(func.count()).select_from(DocumentText)) or 0),
        },
    }


def write_quality_exports(db, experiment_id: UUID, output_dir: Path, scope: dict) -> None:
    runs_by_id = {run.id: run for run in scope["runs"]}
    turns_by_id = {turn.id: turn for turn in scope["turns"]}
    outputs = [
        output
        for output in experiment_result_repository.list_outputs(db, experiment_id)
        if output.turn_id in turns_by_id
    ]
    output_to_turn = {output.id: turns_by_id.get(output.turn_id) for output in outputs}
    scoped_output_ids = {output.id for output in outputs}
    claims = [
        claim
        for claim in experiment_result_repository.list_claims(db, experiment_id)
        if claim.output_id in scoped_output_ids
    ]
    retrieval_items = [
        (turn_id, item)
        for turn_id, item in experiment_result_repository.list_retrieval_items(db, experiment_id)
        if turn_id in turns_by_id
    ]
    retrieval_rows = []

    for turn_id, item in retrieval_items:
        turn = turns_by_id.get(turn_id)
        run = runs_by_id.get(turn.system_run_id) if turn else None
        retrieval_rows.append(
            {
                "turn_id": str(turn_id),
                "system": run.system_type if run else None,
                "rank": item.rank,
                "canonical_source_id": str(item.canonical_source_id) if item.canonical_source_id else None,
                "raw_score": item.raw_score,
                "normalized_score": item.normalized_score,
                "source_type": item.source_type,
                "document_id": str(item.document_id) if item.document_id else None,
                "token_count": item.token_count,
                "content_preview": item.content_preview,
            }
        )

    write_json(output_dir / "retrieval_traces.json", retrieval_rows)
    write_json(output_dir / "activation_traces.json", [row for row in retrieval_rows if row["system"] == "csm"])

    claim_rows = []

    for claim in claims:
        turn = output_to_turn.get(claim.output_id)
        run = runs_by_id.get(turn.system_run_id) if turn else None
        status = claim.source_support_status or (claim.normalized_claim or {}).get("source_support_status")
        claim_rows.append(
            {
                "claim_id": claim.claim_id,
                "claim_uuid": str(claim.id),
                "turn_id": str(turn.id) if turn else None,
                "system": run.system_type if run else None,
                "repetition": run.repetition_number if run else None,
                "claim_text": claim.claim_text,
                "confidence": claim.confidence,
                "citation_ids": json.dumps(claim.citation_ids),
                "source_support_status": status,
            }
        )

    write_csv(output_dir / "claims_audit.csv", claim_rows)
    write_csv(output_dir / "unsupported_claims.csv", [row for row in claim_rows if row["source_support_status"] in {"unsupported", "contradicted"}])
    write_csv(output_dir / "hallucinations.csv", [row for row in claim_rows if row["source_support_status"] in {"unsupported", "contradicted"}])

    citation_rows = []

    for output in outputs:
        turn = turns_by_id.get(output.turn_id)
        run = runs_by_id.get(turn.system_run_id) if turn else None

        for citation in output.citations or []:
            citation_rows.append(
                {
                    "output_id": str(output.id),
                    "turn_id": str(turn.id) if turn else None,
                    "system": run.system_type if run else None,
                    "citation_id": citation.get("citation_id") or citation.get("source_id") or citation.get("canonical_source_id"),
                    "canonical_source_id": citation.get("canonical_source_id"),
                    "document_id": citation.get("document_id"),
                    "source_type": citation.get("source_type"),
                    "classification": citation.get("classification") or citation.get("support_status") or "stored_unclassified",
                }
            )

    write_csv(output_dir / "citations_audit.csv", citation_rows)
    write_csv(output_dir / "failed_turns.csv", failed_turns(db, experiment_id, scope))
    write_csv(output_dir / "temporal_errors.csv", metric_detail_rows(db, experiment_id, "temporal_consistency", scope))
    write_csv(output_dir / "future_leakage_audit.csv", [row for row in metric_detail_rows(db, experiment_id, "temporal_consistency", scope) if "future" in json.dumps(row).lower()])
    write_csv(output_dir / "contradiction_results.csv", metric_detail_rows(db, experiment_id, "contradiction_handling", scope))
    write_csv(output_dir / "correction_recovery_results.csv", metric_detail_rows(db, experiment_id, "correction_recovery", scope))
    write_csv(output_dir / "state_transition_results.csv", metric_detail_rows(db, experiment_id, "memory_update_accuracy", scope))
    write_json(output_dir / "csm_state_trace.json", csm_state_trace(db))
    write_json(output_dir / "csm_lineage_trace.json", csm_lineage_trace(db))
    write_csv(output_dir / "pending_review_results.csv", pending_review_rows(db))


def write_efficiency_exports(db, experiment_id: UUID, output_dir: Path, scope: dict) -> None:
    llm_rows = []
    scoped_turn_ids = scope["turn_ids"]

    for turn_id, call in experiment_result_repository.list_llm_calls(db, experiment_id):
        if turn_id not in scoped_turn_ids:
            continue
        cost = estimate_token_cost(
            provider=call.provider,
            model=call.model,
            input_tokens=call.input_token_count,
            output_tokens=call.output_token_count,
        )
        llm_rows.append(
            {
                "turn_id": str(turn_id),
                "llm_call_id": str(call.id),
                "task_type": call.task_type,
                "provider": call.provider,
                "model": call.model,
                "input_tokens": call.input_token_count,
                "output_tokens": call.output_token_count,
                "total_tokens": call.total_token_count,
                "duration_ms": call.duration_ms,
                "request_status": call.request_status,
                "estimated_cost_usd": cost.get("total_cost"),
            }
        )

    write_csv(output_dir / "token_results.csv", llm_rows)
    write_csv(output_dir / "latency_results.csv", [{"turn_id": row["turn_id"], "llm_call_id": row["llm_call_id"], "duration_ms": row["duration_ms"]} for row in llm_rows])
    write_csv(output_dir / "cost_results.csv", llm_rows)
    write_csv(output_dir / "online_query_cost.csv", [row for row in llm_rows if row["task_type"] == "grounded_answer"])
    write_csv(output_dir / "offline_maintenance_cost.csv", [row for row in llm_rows if row["task_type"] != "grounded_answer"])


def write_paper_exports(output_dir: Path, metric_summary: dict, rankings: dict, statistics: list[dict], manifest: dict) -> None:
    main_rows = paper_rows(metric_summary, MAIN_METRICS)
    write_csv(output_dir / "paper_main_results_table.csv", main_rows)
    write_text(output_dir / "paper_main_results_table.md", markdown_table(main_rows))
    write_text(output_dir / "paper_main_results_table.tex", latex_table(main_rows))

    for group, metrics in PAPER_METRIC_GROUPS.items():
        rows = paper_rows(metric_summary, metrics)
        write_csv(output_dir / f"paper_{group}_table.csv", rows)
        write_text(output_dir / f"paper_{group}_table.md", markdown_table(rows))
        write_text(output_dir / f"paper_{group}_table.tex", latex_table(rows))

    stat_rows = [
        {
            "metric_name": row["metric_name"],
            "system_a": row["system_a"],
            "system_b": row["system_b"],
            "sample_count": row["sample_count"],
            "raw_p_value": row["raw_p_value"],
            "corrected_p_value": row["corrected_p_value"],
            "effect_size": row["effect_size"],
        }
        for row in statistics
    ]
    write_csv(output_dir / "paper_statistical_comparison_table.csv", stat_rows)
    write_text(output_dir / "paper_statistical_comparison_table.md", markdown_table(stat_rows))
    write_text(output_dir / "paper_statistical_comparison_table.tex", latex_table(stat_rows))
    write_csv(output_dir / "paper_ablation_placeholder_table.csv", [{"status": "not_run", "reason": "No ablation protocol was executed in this pilot run."}])
    write_text(output_dir / "paper_results_summary.md", paper_summary(rankings, manifest))
    write_text(output_dir / "paper_failure_analysis.md", failure_analysis(manifest))
    write_text(output_dir / "paper_experimental_setup.md", experimental_setup(manifest))
    write_text(output_dir / "paper_limitations.md", limitations_text(manifest))


def paper_rows(summary: dict, metric_ids: list[str]) -> list[dict]:
    rows = []

    for system, metrics in summary.items():
        row = {"System": system}

        for metric_id in metric_ids:
            item = metrics.get(metric_id, {})
            row[metric_id] = format_score(item)

        rows.append(row)

    return rows


def format_score(item: dict) -> str:
    if not item or item.get("mean") is None:
        return "N/A"

    low = item.get("ci95_low")
    high = item.get("ci95_high")

    if low is None or high is None:
        return f"{item['mean']:.4g}"

    half_width = max(abs(item["mean"] - low), abs(high - item["mean"]))
    return f"{item['mean']:.4g} +/- {half_width:.4g}"


def paper_summary(rankings: dict, manifest: dict) -> str:
    lines = [
        "# Sustha Three-Patient Pilot Results",
        "",
        "This is a synthetic pilot/integration benchmark. It should not be interpreted as evidence of broad clinical generalization.",
        "",
        f"Experiment status: `{manifest.get('status')}`.",
        f"Completed turns: `{manifest.get('progress', {}).get('completed_turns')}` of `{manifest.get('progress', {}).get('expected_turns')}`.",
        f"Measured metric rows: `{manifest.get('measured_metric_rows')}`.",
        "",
        "## Top Systems By Metric",
    ]

    for metric_name, rows in rankings.items():
        top = rows[:3]

        if not top:
            lines.append(f"- `{metric_name}`: no measured systems.")
            continue

        rendered = ", ".join(f"{row['system']} ({row['score']:.4g})" for row in top)
        lines.append(f"- `{metric_name}`: {rendered}.")

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "Rankings are based on measured database metric rows and confidence intervals. Ties are flagged in `metric_rankings.json` where confidence intervals overlap.",
        ]
    )
    return "\n".join(lines) + "\n"


def failure_analysis(manifest: dict) -> str:
    failure_reason = manifest.get("failure_reason") or "No experiment-level failure reason was recorded."
    return f"# Failure Analysis\n\n{failure_reason}\n\nFailed turns are listed in `failed_turns.csv`.\n"


def experimental_setup(manifest: dict) -> str:
    return (
        "# Experimental Setup\n\n"
        "The run imports the synthetic Sustha three-patient evaluation pack, initializes the configured memory systems, "
        "runs independent single-turn questions with controlled source cutoffs, stores retrieval traces and LLM outputs, "
        "refreshes metric rows, computes paired statistics, and writes paper-ready exports from the database.\n\n"
        f"Systems: `{', '.join(manifest.get('systems') or [])}`.\n"
    )


def limitations_text(manifest: dict) -> str:
    return (
        "# Limitations\n\n"
        "- The benchmark contains three synthetic patients and is suitable for integration/pilot analysis only.\n"
        "- Any failed system run or turn must be interpreted from the exported failure files, not converted into a zero score.\n"
        "- Metrics marked `N/A` were not applicable or lacked required inputs under the stored protocol.\n"
    )


def failed_turns(db, experiment_id: UUID, scope: dict) -> list[dict]:
    rows = []
    runs_by_id = {run.id: run for run in scope["runs"]}
    questions_by_id = scope["questions_by_id"]

    for turn in scope["turns"]:
        if turn.status != "failed":
            continue

        run = runs_by_id.get(turn.system_run_id)
        question = questions_by_id.get(turn.question_id)
        rows.append(
            {
                "turn_id": str(turn.id),
                "system": run.system_type if run else None,
                "repetition": run.repetition_number if run else None,
                "question": question.question if question else None,
                "source_cutoff": iso(question.source_cutoff) if question else None,
            }
        )

    return rows


def metric_detail_rows(db, experiment_id: UUID, metric_name: str, scope: dict) -> list[dict]:
    rows = []
    runs_by_id = {run.id: run for run in scope["runs"]}

    for result in scope["metrics"]:
        if result.metric_name != metric_name:
            continue

        run = runs_by_id.get(result.system_run_id)
        rows.append(
            {
                "system": run.system_type if run else None,
                "repetition": run.repetition_number if run else None,
                "metric_name": result.metric_name,
                "value": result.value,
                "applicable": result.applicable,
                "reason_not_applicable": result.reason_not_applicable,
                "details": json.dumps(result.details or {}, sort_keys=True),
            }
        )

    return rows


def csm_state_trace(db) -> list[dict]:
    try:
        from app.memory_systems.csm.models import CsmStateVariable
    except Exception:
        return []

    return [
        {
            "id": str(row.id),
            "system_instance_id": str(row.system_instance_id),
            "state_type": row.state_type,
            "state_key": row.state_key,
            "current_value": row.current_value,
            "confidence": row.confidence,
            "status": row.status,
            "valid_from": iso(row.valid_from),
            "valid_to": iso(row.valid_to),
            "last_updated_at": iso(row.last_updated_at),
            "created_at": iso(row.created_at),
        }
        for row in db.scalars(select(CsmStateVariable)).all()
    ]


def csm_lineage_trace(db) -> list[dict]:
    try:
        from app.memory_systems.csm.models import CsmStateEvidenceLink
    except Exception:
        return []

    return [
        {
            "state_variable_id": str(row.state_variable_id),
            "evidence_id": str(row.evidence_id),
            "contribution_type": row.contribution_type,
            "contribution_weight": row.contribution_weight,
            "created_at": iso(row.created_at),
        }
        for row in db.scalars(select(CsmStateEvidenceLink)).all()
    ]


def pending_review_rows(db) -> list[dict]:
    try:
        from app.memory_systems.csm.models import CsmReviewRequest
    except Exception:
        return []

    return [
        {
            "id": str(row.id),
            "system_instance_id": str(row.system_instance_id),
            "canonical_source_id": str(row.canonical_source_id),
            "status": getattr(row, "status", None),
            "review_type": getattr(row, "review_type", None),
            "reason": getattr(row, "reason", None) or getattr(row, "rationale", None),
            "created_at": iso(getattr(row, "created_at", None)),
        }
        for row in db.scalars(select(CsmReviewRequest)).all()
    ]


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()})

    with path.open("w", newline="", encoding="utf-8") as handle:
        if not fieldnames:
            handle.write("")
            return

        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            writer.writerow({key: json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else value for key, value in row.items()})


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str, sort_keys=True), encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def markdown_table(rows: list[dict]) -> str:
    if not rows:
        return "_No rows._\n"

    headers = list(rows[0].keys())
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]

    for row in rows:
        lines.append("| " + " | ".join(str(row.get(header, "")) for header in headers) + " |")

    return "\n".join(lines) + "\n"


def latex_table(rows: list[dict]) -> str:
    if not rows:
        return "% No rows.\n"

    headers = list(rows[0].keys())
    lines = ["\\begin{tabular}{" + "l" * len(headers) + "}", " & ".join(headers) + " \\\\", "\\hline"]

    for row in rows:
        lines.append(" & ".join(str(row.get(header, "")).replace("_", "\\_") for header in headers) + " \\\\")

    lines.append("\\end{tabular}")
    return "\n".join(lines) + "\n"


def iso(value) -> str | None:
    return value.isoformat() if value else None


if __name__ == "__main__":
    raise SystemExit(main())
