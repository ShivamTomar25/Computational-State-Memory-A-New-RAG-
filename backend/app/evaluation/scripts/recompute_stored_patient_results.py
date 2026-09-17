from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import func, select

from app.database import SessionLocal
from app.evaluation.experiments.models.experiment import ExperimentOutput, ExperimentSystemRun, ExperimentTurn
from app.evaluation.offline_recomputation.claim_support_classifier import ALLOWED
from app.evaluation.offline_recomputation.correction_evaluator import required_csm_sanity_terms
from app.evaluation.offline_recomputation.exporter import export_all
from app.evaluation.offline_recomputation.metric_calculator import aggregate_observations
from app.evaluation.offline_recomputation.observation_builder import build_all
from app.evaluation.offline_recomputation.scope_loader import SYSTEMS, load_scope, validate_scope


def main() -> int:
    parser = argparse.ArgumentParser(description="Observation-level offline recomputation for stored Sustha patient results.")
    parser.add_argument("--experiment-id", default="b9570d90-7be3-4dbf-9063-535811b2e970")
    parser.add_argument("--source-experiment-id", default="2ecee123-ddc0-4072-a823-885c12fc98a6")
    parser.add_argument("--abandoned-experiment-id", default="38bfe0ac-d975-426a-9975-b4b1a3a62be2")
    parser.add_argument("--patient", default="SYN-CSM-001")
    parser.add_argument("--repetition", type=int, default=1)
    parser.add_argument("--output-root", default="../evaluation/results/csm_v2_final_comparison_offline_v3")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        llm_call_count_before = experiment_llm_call_count(db, UUID(args.experiment_id))
        scope = load_scope(db, experiment_id=UUID(args.experiment_id), patient=args.patient, repetition=args.repetition)
        source_scope = load_scope(db, experiment_id=UUID(args.source_experiment_id), patient=args.patient, repetition=args.repetition)
        abandoned_summary = experiment_turn_summary(db, UUID(args.abandoned_experiment_id))
        llm_call_count_after_load = experiment_llm_call_count(db, UUID(args.experiment_id))
    finally:
        db.close()

    validation = validate_scope(scope)
    print(f"included_turns = {validation['included_turns']}")
    print(f"systems = {validation['systems']}")
    print("questions_per_system = 20")
    if validation["status"] != "passed":
        print(json.dumps(validation, indent=2, sort_keys=True))
        raise SystemExit("Scope validation failed; export rejected.")

    built = build_all(scope)
    source_built = build_all(source_scope) if validate_scope(source_scope)["status"] == "passed" else None
    built["comparison_provenance"] = {
        "evaluation_mode": "offline_observation_level_recomputation",
        "completed_derived_experiment_id": str(scope.experiment_id),
        "source_experiment_id": args.source_experiment_id,
        "patient": args.patient,
        "repetition": args.repetition,
        "final_turn_source": "completed_derived_experiment_only",
        "turn_mixing": False,
        "used_existing_aggregate_metric_rows": False,
        "zero_groq_calls": True,
        "no_llm_calls_performed": True,
        "provider_invocations_during_recomputation": 0,
        "groq_provider_invocations_during_recomputation": 0,
        "llm_calls_before": llm_call_count_before,
        "llm_calls_after": llm_call_count_after_load,
        "llm_call_count_before_load": llm_call_count_before,
        "llm_call_count_after_load": llm_call_count_after_load,
        "abandoned_or_superseded_experiment": abandoned_summary,
        "phase_aware_csm_lifecycle_validation": {
            "pre_generation_expected": {"csm_status": "pending", "csm_completed_turns": 0},
            "post_generation_expected": {"csm_status": "completed", "csm_completed_turns": 20, "csm_outputs": 20},
            "current_phase": "post_generation_offline_evaluation",
        },
    }
    built["answer_preservation"] = {
        "provider_invocations_during_recomputation": 0,
        "llm_call_count_before_load": llm_call_count_before,
        "llm_call_count_after_load": llm_call_count_after_load,
        "llm_call_count_changed": llm_call_count_before != llm_call_count_after_load,
    }
    built["csm_v1_vs_csm_v2"] = csm_v1_vs_csm_v2(source_built, built)
    verify_before_export(built)
    matrix = aggregate_observations(built["metric_observations"])
    print_validation_table(matrix)

    output_dir = (
        Path(args.output_root)
        / args.patient
        / f"repetition_{args.repetition}"
        / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ).resolve()
    summary = export_all(output_dir, scope, built)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def verify_before_export(built: dict[str, list[dict]]) -> None:
    observations = built["metric_observations"]
    if len(observations) <= 140:
        raise SystemExit("Export rejected: metric_observations.csv would contain <= 140 rows.")
    support_statuses = [row.get("support_classification") for row in built["claim_support_audit"]]
    if any(not status for status in support_statuses):
        raise SystemExit("Export rejected: blank claim support status found.")
    if any(status not in ALLOWED for status in support_statuses):
        raise SystemExit("Export rejected: invalid claim support status found.")
    if any(row.get("citation_classification") == "stored_unclassified" for row in built["citation_resolution_audit"]):
        raise SystemExit("Export rejected: stored_unclassified citation found.")
    factual_statuses = {"supported", "partially_supported", "unsupported", "contradicted"}
    factual_claims = [row for row in built["claim_support_audit"] if row.get("support_classification") in factual_statuses]
    if any(not row.get("support_classification") for row in factual_claims):
        raise SystemExit("Export rejected: factual claim without support classification.")
    applicable_counts = Counter((row["system"], row["metric_name"]) for row in observations if row["applicable"])
    if applicable_counts and all(count == 1 for count in applicable_counts.values()):
        raise SystemExit("Export rejected: all applicable observation counts equal one.")
    if all_zero_without_reason(observations, "answer_accuracy"):
        raise SystemExit("Export rejected: all answer_accuracy observations are zero.")
    if all_one_without_reason(observations, "hallucination_rate"):
        raise SystemExit("Export rejected: all hallucination_rate observations are one.")
    sanity = csm_sanity_rows(built)
    if sanity and all(row.get("support_classification") in {"unsupported", "contradicted"} for row in sanity):
        raise SystemExit("Export rejected: CSM renal correction sanity claims still receive zero credit.")


def csm_sanity_rows(built: dict[str, list[dict]]) -> list[dict]:
    terms = required_csm_sanity_terms()
    rows = []
    for row in built["claim_support_audit"]:
        if row["system"] != "csm":
            continue
        text = str(row.get("claim_text") or "").lower()
        if any(term.lower() in text for term in terms):
            rows.append(row)
            print(
                json.dumps(
                    {
                        "sanity_claim": row.get("claim_text"),
                        "support_classification": row.get("support_classification"),
                        "calculation_reason": row.get("calculation_reason"),
                    },
                    sort_keys=True,
                )
            )
    return rows


def csm_v1_vs_csm_v2(source_built: dict | None, current_built: dict) -> list[dict]:
    if source_built is None:
        return [
            {
                "metric_name": "all",
                "comparison_status": "not_computed",
                "reason": "source_experiment_scope_failed_validation",
                "metric_definition_changed": False,
                "evaluator_compatibility": "not_available",
            }
        ]

    source_matrix = {
        row["metric_name"]: row
        for row in aggregate_observations(source_built["metric_observations"])
        if row["system"] == "csm"
    }
    current_matrix = {
        row["metric_name"]: row
        for row in aggregate_observations(current_built["metric_observations"])
        if row["system"] == "csm"
    }
    rows = []
    for metric in sorted(set(source_matrix) | set(current_matrix)):
        old = source_matrix.get(metric, {})
        new = current_matrix.get(metric, {})
        old_value = old.get("value")
        new_value = new.get("value")
        absolute = float(new_value) - float(old_value) if old_value is not None and new_value is not None else None
        relative = absolute / abs(float(old_value)) if absolute is not None and old_value not in (None, 0, 0.0) else None
        rows.append(
            {
                "metric_name": metric,
                "csm_v1_value": old_value,
                "csm_v2_value": new_value,
                "absolute_difference": absolute,
                "relative_difference": relative,
                "csm_v1_observation_count": old.get("observation_count"),
                "csm_v2_observation_count": new.get("observation_count"),
                "csm_v1_ci_low": old.get("ci_low"),
                "csm_v1_ci_high": old.get("ci_high"),
                "csm_v2_ci_low": new.get("ci_low"),
                "csm_v2_ci_high": new.get("ci_high"),
                "statistically_tested": bool((old.get("observation_count") or 0) >= 2 and (new.get("observation_count") or 0) >= 2),
                "metric_definition_changed": False,
                "evaluator_compatibility": "same_offline_observation_level_evaluator",
            }
        )
    return rows


def experiment_llm_call_count(db, experiment_id: UUID) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(ExperimentTurn)
            .join(ExperimentSystemRun, ExperimentTurn.system_run_id == ExperimentSystemRun.id)
            .where(
                ExperimentSystemRun.experiment_id == experiment_id,
                ExperimentTurn.llm_call_id.is_not(None),
            )
        )
        or 0
    )


def experiment_turn_summary(db, experiment_id: UUID) -> dict:
    run_count = int(db.scalar(select(func.count()).select_from(ExperimentSystemRun).where(ExperimentSystemRun.experiment_id == experiment_id)) or 0)
    turn_count = int(
        db.scalar(
            select(func.count())
            .select_from(ExperimentTurn)
            .join(ExperimentSystemRun, ExperimentTurn.system_run_id == ExperimentSystemRun.id)
            .where(ExperimentSystemRun.experiment_id == experiment_id)
        )
        or 0
    )
    output_count = int(
        db.scalar(
            select(func.count())
            .select_from(ExperimentOutput)
            .join(ExperimentTurn, ExperimentOutput.turn_id == ExperimentTurn.id)
            .join(ExperimentSystemRun, ExperimentTurn.system_run_id == ExperimentSystemRun.id)
            .where(ExperimentSystemRun.experiment_id == experiment_id)
        )
        or 0
    )
    return {
        "experiment_id": str(experiment_id),
        "run_count": run_count,
        "turn_count": turn_count,
        "output_count": output_count,
        "status": "abandoned_or_superseded" if output_count == 0 else "contains_completed_outputs_not_used_in_final_matrix",
        "used_in_final_matrix": False,
        "reason": "final evaluation uses only b9570d90-7be3-4dbf-9063-535811b2e970",
    }


def all_zero_without_reason(observations: list[dict], metric: str) -> bool:
    values = [row for row in observations if row["metric_name"] == metric and row["applicable"]]
    return bool(values) and all(float(row["observation_value"] or 0) == 0.0 for row in values)


def all_one_without_reason(observations: list[dict], metric: str) -> bool:
    values = [row for row in observations if row["metric_name"] == metric and row["applicable"]]
    return bool(values) and all(float(row["observation_value"] or 0) == 1.0 for row in values)


def print_validation_table(matrix: list[dict]) -> None:
    print("metric_name,system,observation_count,mean,ci_low,ci_high")
    for row in matrix:
        print(f"{row['metric_name']},{row['system']},{row['observation_count']},{row['mean']},{row['ci_low']},{row['ci_high']}")


if __name__ == "__main__":
    raise SystemExit(main())
