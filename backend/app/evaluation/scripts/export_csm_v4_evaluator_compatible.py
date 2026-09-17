from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import func, select

from app.database import SessionLocal
from app.evaluation.metrics.registry.registry import list_metric_definitions
from app.evaluation.offline_recomputation.exporter import PAPER_21_METRICS
from app.evaluation.offline_recomputation.metric_calculator import METRICS, aggregate_value
from app.evaluation.offline_recomputation.observation_builder import build_all
from app.evaluation.offline_recomputation.scope_loader import load_scope, validate_scope
from app.evaluation.offline_recomputation.statistics import LOWER_IS_BETTER, paired_comparisons
from app.evaluation.scripts.export_csm_v3_evaluator_compatible import (
    BASELINE_DIRS,
    BASELINE_SYSTEMS,
    CSM_V3_EXPERIMENT_ID,
    PATIENTS,
    aggregate_metric,
    answer_digest,
    empty_to_none,
    flatten_built,
    format_cell,
    frozen_baseline_hashes,
    markdown_table,
    read_csv,
    to_float,
    truth_digest,
    write_csv,
    write_json,
    write_text,
)
from app.llm.common.models.llm import LlmCall


CSM_V4_EXPERIMENT_ID = UUID("179bb8b4-2640-4619-89cb-3cd509e7c8e7")
REPORT_SYSTEMS = [
    "long_context",
    "rolling_summary",
    "dense_rag",
    "hybrid_rag",
    "graph_rag",
    "hippo_rag",
    "csm_v2",
    "csm_v3",
    "csm_v4",
]
STAT_SYSTEMS = [
    "long_context",
    "rolling_summary",
    "dense_rag",
    "hybrid_rag",
    "graph_rag",
    "hippo_rag",
    "csm",
    "csm_v3",
    "csm_v4",
]

METRIC_CATEGORIES = {
    "state_accuracy": "STATE",
    "memory_update_accuracy": "STATE",
    "state_recovery_time": "STATE",
    "temporal_consistency": "TEMPORAL",
    "correction_recovery": "TEMPORAL",
    "decision_f1": "QUALITY",
    "answer_accuracy": "QUALITY",
    "expected_calibration_error": "QUALITY",
    "contradiction_handling": "QUALITY",
    "hallucination_rate": "GROUNDING",
    "evidence_support_rate": "GROUNDING",
    "unsupported_claim_rate": "GROUNDING",
    "fabricated_citation_rate": "GROUNDING",
    "faithfulness": "GROUNDING",
    "groundedness": "GROUNDING",
    "lineage_citation_f1": "GROUNDING",
    "retrieval_precision": "RETRIEVAL",
    "retrieval_recall": "RETRIEVAL",
    "activation_precision": "RETRIEVAL",
    "activation_recall": "RETRIEVAL",
    "tokens_per_query": "EFFICIENCY",
    "p95_latency": "EFFICIENCY",
    "provider_generation_latency_ms": "EFFICIENCY",
    "retrieval_activation_latency_ms": "EFFICIENCY",
    "processing_latency_ms": "EFFICIENCY",
    "operational_wall_clock_latency_ms": "EFFICIENCY",
    "total_cost": "COST",
    "online_query_cost": "COST",
    "offline_csm_update_cost": "COST",
}

CODE_FILES_CHANGED = [
    "backend/app/memory_systems/csm/v4_engine.py",
    "backend/app/memory_systems/csm/v4_adapter.py",
    "backend/app/config.py",
    "backend/app/memory_systems/common/enums/status.py",
    "backend/app/memory_systems/common/registry/registry.py",
    "backend/app/memory_systems/common/services/memory_service.py",
    "backend/app/memory_systems/common/canonical/source_collector.py",
    "backend/app/evaluation/experiments/services/live_runner.py",
    "backend/app/evaluation/offline_recomputation/scope_loader.py",
    "backend/app/evaluation/offline_recomputation/statistics.py",
    "backend/app/evaluation/offline_recomputation/observation_builder.py",
    "backend/app/evaluation/offline_recomputation/metric_calculator.py",
    "backend/app/evaluation/scripts/diagnose_csm_v2_vs_v3_questions.py",
    "backend/app/evaluation/scripts/preflight_csm_v4_offline_gates.py",
    "backend/app/evaluation/scripts/export_csm_v4_evaluator_compatible.py",
    "backend/tests/memory_systems/test_csm_v4_engine.py",
    "backend/tests/memory_systems/test_memory_registry.py",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Export CSM v4 evaluator-compatible offline metrics without provider calls.")
    parser.add_argument("--experiment-id", default=str(CSM_V4_EXPERIMENT_ID))
    parser.add_argument("--csm-v3-experiment-id", default=str(CSM_V3_EXPERIMENT_ID))
    parser.add_argument("--output-root", default="../evaluation/results/csm_v4_evaluator_compatible")
    parser.add_argument("--tests-note", default="Tests not supplied to exporter.")
    args = parser.parse_args()

    v4_experiment_id = UUID(args.experiment_id)
    v3_experiment_id = UUID(args.csm_v3_experiment_id)

    metric_definitions = {definition.metric_id: definition for definition in list_metric_definitions()}
    metric_set = set(METRICS) | set(PAPER_21_METRICS)
    directions = {metric: ("lower_is_better" if metric in LOWER_IS_BETTER else "higher_is_better") for metric in metric_set}
    directions.update({metric: definition.direction.value for metric, definition in metric_definitions.items()})
    aggregations = {metric: "sum" if metric == "total_cost" else "p95" if metric == "p95_latency" else "mean" for metric in metric_set}
    aggregations.update({metric: definition.aggregation_method for metric, definition in metric_definitions.items()})
    metric_order = [metric for metric in METRICS if metric in metric_set]

    backend_dir = Path(__file__).resolve().parents[3]
    baseline_dirs = {patient: (backend_dir / relative).resolve() for patient, relative in BASELINE_DIRS.items()}
    baseline_hashes_before = frozen_baseline_hashes(baseline_dirs)
    baseline_matrix_by_patient = {
        patient: {(row["system"], row["metric_name"]): row for row in read_csv(directory / "system_metric_matrix.csv")}
        for patient, directory in baseline_dirs.items()
    }
    baseline_observations = []
    baseline_scope_validation = {}
    for patient, directory in baseline_dirs.items():
        baseline_observations.extend(read_csv(directory / "metric_observations.csv"))
        baseline_scope_validation[patient] = json.loads((directory / "scope_validation.json").read_text())

    with SessionLocal() as db:
        llm_calls_before = int(db.scalar(select(func.count()).select_from(LlmCall)) or 0)
        answers_before = answer_digest(db)
        truth_before = truth_digest(db)
        v3_built = {}
        v4_built = {}
        v3_scopes = {}
        v4_scopes = {}
        v3_validations = {}
        v4_validations = {}
        for patient in PATIENTS:
            v3_scope = load_scope(db, experiment_id=v3_experiment_id, patient=patient, repetition=1)
            v4_scope = load_scope(db, experiment_id=v4_experiment_id, patient=patient, repetition=1)
            v3_validation = validate_scope(v3_scope)
            v4_validation = validate_scope(v4_scope)
            v3_validations[patient] = v3_validation
            v4_validations[patient] = v4_validation
            if v3_validation["status"] != "passed":
                raise SystemExit(f"CSM v3 scope validation failed for {patient}: {v3_validation}")
            if v4_validation["status"] != "passed":
                raise SystemExit(f"CSM v4 scope validation failed for {patient}: {v4_validation}")
            v3_scopes[patient] = v3_scope
            v4_scopes[patient] = v4_scope
            v3_built[patient] = build_all(v3_scope)
            v4_built[patient] = build_all(v4_scope)
        llm_calls_after = int(db.scalar(select(func.count()).select_from(LlmCall)) or 0)
        answers_after = answer_digest(db)
        truth_after = truth_digest(db)

    v3_observations = [row for patient in PATIENTS for row in v3_built[patient]["metric_observations"]]
    v4_observations = [row for patient in PATIENTS for row in v4_built[patient]["metric_observations"]]
    baseline_hashes_after = frozen_baseline_hashes(baseline_dirs)
    new_llm_calls = llm_calls_after - llm_calls_before

    output_dir = Path(args.output_root) / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)

    write_text(output_dir / "01_csm_v4_implementation_summary.md", implementation_summary_text())
    write_text(output_dir / "02_tests.txt", args.tests_note)
    write_csv(output_dir / "03_v4_claim_mapping_audit.csv", flatten_built(v4_built, "claim_support_audit"))
    write_csv(output_dir / "04_v4_citation_resolution_audit.csv", flatten_built(v4_built, "citation_resolution_audit"))
    write_csv(output_dir / "05_v4_state_observation_mapping.csv", metric_rows(v4_observations, {"state_accuracy", "memory_update_accuracy", "state_recovery_time"}))
    write_csv(output_dir / "06_v4_temporal_mapping.csv", metric_rows(v4_observations, {"temporal_consistency", "decision_f1", "correction_recovery"}))
    write_csv(output_dir / "07_v4_activation_mapping.csv", metric_rows(v4_observations, {"activation_precision", "activation_recall"}))

    patient_matrix_rows = {}
    for index, patient in enumerate(PATIENTS, start=1):
        rows = patient_matrix(
            patient,
            baseline_matrix_by_patient[patient],
            v3_built[patient]["metric_observations"],
            v4_built[patient]["metric_observations"],
            metric_order,
            directions,
            aggregations,
        )
        patient_matrix_rows[patient] = rows
        write_csv(output_dir / f"{7 + index:02d}_patient_{index}_v2_v3_v4_matrix.csv", rows)

    pooled = overall_matrix(baseline_observations, v3_observations, v4_observations, metric_order, directions, aggregations)
    macro = macro_matrix(patient_matrix_rows, metric_order, directions, aggregations)
    comparison = csm_v2_v3_v4_comparison(pooled, directions)
    rankings = all_system_rankings(pooled, directions)
    stats = [
        row
        for row in paired_comparisons(baseline_observations + v3_observations + v4_observations, STAT_SYSTEMS)
        if row["comparison"].startswith("csm_v4_vs_")
    ]

    write_csv(output_dir / "11_overall_pooled_matrix.csv", pooled)
    write_csv(output_dir / "12_overall_macro_matrix.csv", macro)
    write_csv(output_dir / "13_csm_v2_v3_v4_comparison.csv", comparison)
    write_csv(output_dir / "14_all_system_rankings.csv", rankings)
    write_csv(output_dir / "15_statistical_comparisons.csv", stats)

    validation = {
        "experiment_id": str(v4_experiment_id),
        "csm_v3_experiment_id": str(v3_experiment_id),
        "patients": len(PATIENTS),
        "questions": 60,
        "systems_in_final_comparison": len(REPORT_SYSTEMS),
        "csm_v3_completed_turns": sum(item["completed_turns"] for item in v3_validations.values()),
        "csm_v4_completed_turns": sum(item["completed_turns"] for item in v4_validations.values()),
        "new_llm_calls_during_export": new_llm_calls,
        "stored_answers_modified": answers_before != answers_after,
        "ground_truth_modified": truth_before != truth_after,
        "metric_formulas_modified_by_exporter": False,
        "baseline_values_changed": baseline_hashes_before != baseline_hashes_after,
        "baseline_hashes_before": baseline_hashes_before,
        "baseline_hashes_after": baseline_hashes_after,
        "baseline_scope_validation": baseline_scope_validation,
        "csm_v3_scope_validation": v3_validations,
        "csm_v4_scope_validation": v4_validations,
        "output_dir": str(output_dir),
    }
    write_json(output_dir / "16_final_scientific_validation.json", validation)
    write_text(output_dir / "17_final_report.md", final_report(output_dir, validation, pooled, comparison, rankings, stats, args.tests_note))

    print(json.dumps({"status": "completed", "output_dir": str(output_dir), "new_llm_calls_during_export": new_llm_calls}, indent=2))
    return 0


def implementation_summary_text() -> str:
    return "\n".join(
        [
            "# CSM v4 Evaluator-Compatible Export",
            "",
            "- Exports stored CSM v4 live answers through the existing offline evaluator path.",
            "- Reuses frozen CSM v2/baseline artifacts and stored CSM v3 answers.",
            "- Refuses to export unless every patient has 20 completed CSM v4 turns.",
            "- Performs no provider calls and does not modify stored answers, ground truth, baselines, CSM v2, or CSM v3.",
        ]
    )


def metric_rows(observations: list[dict], metrics: set[str]) -> list[dict]:
    return [row for row in observations if row["metric_name"] in metrics]


def patient_matrix(
    patient: str,
    baseline_matrix: dict,
    csm_v3_observations: list[dict],
    csm_v4_observations: list[dict],
    metrics: list[str],
    directions: dict,
    aggregations: dict,
) -> list[dict]:
    csm_v3_by_metric = defaultdict(list)
    csm_v4_by_metric = defaultdict(list)
    for row in csm_v3_observations:
        csm_v3_by_metric[row["metric_name"]].append(row)
    for row in csm_v4_observations:
        csm_v4_by_metric[row["metric_name"]].append(row)
    rows = []
    for metric in metrics:
        item = {
            "patient": patient,
            "metric_category": METRIC_CATEGORIES.get(metric, "QUALITY"),
            "metric_name": metric,
            "direction": directions.get(metric),
            "aggregation_function": aggregations.get(metric),
        }
        for system in BASELINE_SYSTEMS:
            output_system = "csm_v2" if system == "csm" else system
            frozen = baseline_matrix.get((system, metric), {})
            item[f"{output_system}_value"] = empty_to_none(frozen.get("value"))
            item[f"{output_system}_n"] = frozen.get("observation_count") or 0
        for system, observations in (("csm_v3", csm_v3_by_metric), ("csm_v4", csm_v4_by_metric)):
            value, n, reason = aggregate_metric(metric, observations.get(metric, []))
            item[f"{system}_value"] = value
            item[f"{system}_n"] = n
            item[f"reason_not_applicable_{system}"] = reason
        rows.append(item)
    return rows


def overall_matrix(
    baseline_observations: list[dict],
    csm_v3_observations: list[dict],
    csm_v4_observations: list[dict],
    metrics: list[str],
    directions: dict,
    aggregations: dict,
) -> list[dict]:
    rows = []
    grouped = defaultdict(list)
    for row in baseline_observations:
        grouped[(row["system"], row["metric_name"])].append(row)
    for row in csm_v3_observations:
        grouped[("csm_v3", row["metric_name"])].append(row)
    for row in csm_v4_observations:
        grouped[("csm_v4", row["metric_name"])].append(row)
    for metric in metrics:
        item = {
            "metric_category": METRIC_CATEGORIES.get(metric, "QUALITY"),
            "metric_name": metric,
            "direction": directions.get(metric),
            "aggregation_function": aggregations.get(metric),
        }
        for system in REPORT_SYSTEMS:
            source_system = "csm" if system == "csm_v2" else system
            value, n, _ = aggregate_metric(metric, grouped.get((source_system, metric), []))
            item[f"{system}_value"] = value
            item[f"{system}_n"] = n
        rows.append(item)
    return rows


def macro_matrix(patient_rows: dict[str, list[dict]], metrics: list[str], directions: dict, aggregations: dict) -> list[dict]:
    rows = []
    for metric in metrics:
        item = {
            "metric_category": METRIC_CATEGORIES.get(metric, "QUALITY"),
            "metric_name": metric,
            "direction": directions.get(metric),
            "aggregation_function": f"macro_patient_{aggregations.get(metric)}",
        }
        for system in REPORT_SYSTEMS:
            values = []
            for rows_for_patient in patient_rows.values():
                row = next(row for row in rows_for_patient if row["metric_name"] == metric)
                value = to_float(row.get(f"{system}_value"))
                if value is not None:
                    values.append(value)
            item[f"{system}_value"] = statistics.mean(values) if values else None
            item[f"{system}_n"] = len(values)
        rows.append(item)
    return rows


def csm_v2_v3_v4_comparison(pooled: list[dict], directions: dict) -> list[dict]:
    rows = []
    baseline_systems = ["long_context", "rolling_summary", "dense_rag", "hybrid_rag", "graph_rag", "hippo_rag"]
    for row in pooled:
        metric = row["metric_name"]
        lower = directions.get(metric) == "lower_is_better"
        v2 = to_float(row.get("csm_v2_value"))
        v3 = to_float(row.get("csm_v3_value"))
        v4 = to_float(row.get("csm_v4_value"))
        baseline_values = [(system, to_float(row.get(f"{system}_value"))) for system in baseline_systems]
        baseline_values = [(system, value) for system, value in baseline_values if value is not None]
        baseline_values.sort(key=lambda item: item[1], reverse=not lower)
        rank = next((item["rank"] for item in all_system_rankings([row], directions) if item["system"] == "csm_v4"), None)
        rows.append(
            {
                "metric_category": METRIC_CATEGORIES.get(metric, "QUALITY"),
                "metric_name": metric,
                "direction": directions.get(metric),
                "csm_v2_value": v2,
                "csm_v3_value": v3,
                "csm_v4_value": v4,
                "best_baseline": baseline_values[0][0] if baseline_values else None,
                "best_baseline_value": baseline_values[0][1] if baseline_values else None,
                "csm_v4_rank": rank,
                **comparison_cells("v4_vs_v2", v4, v2, lower),
                **comparison_cells("v4_vs_v3", v4, v3, lower),
            }
        )
    return rows


def comparison_cells(prefix: str, left: float | None, right: float | None, lower: bool) -> dict[str, float | str | None]:
    diff = left - right if left is not None and right is not None else None
    if diff is None:
        verdict = "not_comparable"
    elif diff == 0:
        verdict = "unchanged"
    elif (diff < 0 and lower) or (diff > 0 and not lower):
        verdict = "improved"
    else:
        verdict = "regressed"
    return {
        f"{prefix}_absolute_difference": diff,
        f"{prefix}_relative_difference_percent": (diff / abs(right) * 100.0) if diff is not None and right not in (None, 0.0) else None,
        f"{prefix}_verdict": verdict,
    }


def all_system_rankings(pooled: list[dict], directions: dict) -> list[dict]:
    rows = []
    for item in pooled:
        metric = item["metric_name"]
        values = []
        for system in REPORT_SYSTEMS:
            value = to_float(item.get(f"{system}_value"))
            if value is not None:
                values.append((system, value, item.get(f"{system}_n")))
        values.sort(key=lambda entry: entry[1], reverse=directions.get(metric) != "lower_is_better")
        last = object()
        rank = 0
        for index, (system, value, n) in enumerate(values, start=1):
            if value != last:
                rank = index
                last = value
            rows.append({"metric_category": METRIC_CATEGORIES.get(metric, "QUALITY"), "metric_name": metric, "direction": directions.get(metric), "rank": rank, "system": system, "value": value, "n": n})
    return rows


def final_report(output_dir: Path, validation: dict, pooled: list[dict], comparison: list[dict], rankings: list[dict], stats: list[dict], tests_note: str) -> str:
    v4_rows = []
    for row in pooled:
        rank = next((item for item in rankings if item["metric_name"] == row["metric_name"] and item["system"] == "csm_v4"), {})
        v4_rows.append([row["metric_category"], row["metric_name"], row.get("csm_v4_value"), row.get("csm_v4_n"), rank.get("rank")])
    comparison_rows = [
        [
            row["metric_category"],
            row["metric_name"],
            row["csm_v2_value"],
            row["csm_v3_value"],
            row["csm_v4_value"],
            row["best_baseline"],
            row["csm_v4_rank"],
            row["v4_vs_v2_verdict"],
            row["v4_vs_v3_verdict"],
        ]
        for row in comparison
    ]
    return "\n".join(
        [
            "# CSM v4 Evaluator-Compatible Offline Report",
            "",
            "## Validation",
            "",
            f"- New LLM calls during export: `{validation['new_llm_calls_during_export']}`",
            f"- Stored answers modified by export: `{'YES' if validation['stored_answers_modified'] else 'NO'}`",
            f"- Ground truth modified by export: `{'YES' if validation['ground_truth_modified'] else 'NO'}`",
            f"- Baseline values changed: `{'YES' if validation['baseline_values_changed'] else 'NO'}`",
            f"- CSM v4 completed turns: `{validation['csm_v4_completed_turns']}`",
            f"- Output directory: `{output_dir}`",
            "",
            "## Code Files Changed",
            "",
            *[f"- `{path}`" for path in CODE_FILES_CHANGED],
            "",
            "## Test Results",
            "",
            tests_note,
            "",
            "## New Result Files",
            "",
            "- `08_patient_1_v2_v3_v4_matrix.csv`",
            "- `09_patient_2_v2_v3_v4_matrix.csv`",
            "- `10_patient_3_v2_v3_v4_matrix.csv`",
            "- `11_overall_pooled_matrix.csv`",
            "- `12_overall_macro_matrix.csv`",
            "- `13_csm_v2_v3_v4_comparison.csv`",
            "- `14_all_system_rankings.csv`",
            "- `15_statistical_comparisons.csv`",
            "",
            "## CSM v4 Pooled Matrix",
            "",
            markdown_table(["Category", "Metric", "CSM v4", "N", "Rank"], v4_rows),
            "",
            "## CSM v2 vs CSM v3 vs CSM v4",
            "",
            markdown_table(["Category", "Metric", "CSM v2", "CSM v3", "CSM v4", "Best Baseline", "V4 Rank", "V4 vs V2", "V4 vs V3"], comparison_rows),
            "",
            f"Statistical comparison rows: `{len(stats)}`.",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
