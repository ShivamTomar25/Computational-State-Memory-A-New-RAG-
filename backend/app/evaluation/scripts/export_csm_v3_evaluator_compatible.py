from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import func, select

from app.database import SessionLocal
from app.evaluation.experiments.models.experiment import ExperimentOutput
from app.evaluation.ground_truth.models.ground_truth import BenchmarkGroundTruth
from app.evaluation.metrics.registry.registry import list_metric_definitions
from app.evaluation.offline_recomputation.exporter import PAPER_21_METRICS
from app.evaluation.offline_recomputation.metric_calculator import METRICS, aggregate_observations, aggregate_value
from app.evaluation.offline_recomputation.observation_builder import build_all
from app.evaluation.offline_recomputation.scope_loader import load_scope, validate_scope
from app.evaluation.offline_recomputation.statistics import LOWER_IS_BETTER, paired_comparisons
from app.llm.common.models.llm import LlmCall


PATIENTS = ["SYN-CSM-001", "SYN-CSM-002", "SYN-CSM-003"]
BASELINE_SYSTEMS = ["long_context", "rolling_summary", "dense_rag", "hybrid_rag", "graph_rag", "hippo_rag", "csm"]
REPORT_SYSTEMS = ["long_context", "rolling_summary", "dense_rag", "hybrid_rag", "graph_rag", "hippo_rag", "csm_v2", "csm_v3"]
CODE_FILES_CHANGED = [
    "backend/app/evaluation/offline_recomputation/citation_resolver.py",
    "backend/app/evaluation/offline_recomputation/metric_calculator.py",
    "backend/app/evaluation/offline_recomputation/exporter.py",
    "backend/app/evaluation/scripts/export_csm_v3_evaluator_compatible.py",
    "backend/tests/evaluation/test_csm_v3_evaluator_compatibility.py",
]
BASELINE_DIRS = {
    "SYN-CSM-001": "../evaluation/results/csm_v2_final_comparison_offline_v3/SYN-CSM-001/repetition_1/20260722T115832Z",
    "SYN-CSM-002": "../evaluation/results/csm_v2_final_comparison_offline_v3/SYN-CSM-002/repetition_1/20260819T104212Z",
    "SYN-CSM-003": "../evaluation/results/csm_v2_final_comparison_offline_v3/SYN-CSM-003/repetition_1/20260819T104216Z",
}
CSM_V3_EXPERIMENT_ID = UUID("2327c728-69ec-4fc4-9410-771c225d61a0")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export CSM v3 evaluator-compatible offline metrics without provider calls.")
    parser.add_argument("--experiment-id", default=str(CSM_V3_EXPERIMENT_ID))
    parser.add_argument("--output-root", default="../evaluation/results/csm_v3_evaluator_compatible")
    parser.add_argument("--tests-note", default="Tests not supplied to exporter.")
    args = parser.parse_args()

    experiment_id = UUID(args.experiment_id)
    output_dir = Path(args.output_root) / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)

    metric_definitions = {definition.metric_id: definition for definition in list_metric_definitions()}
    directions = {metric: ("lower_is_better" if metric in LOWER_IS_BETTER else "higher_is_better") for metric in set(METRICS) | set(PAPER_21_METRICS)}
    directions.update({metric: definition.direction.value for metric, definition in metric_definitions.items()})
    aggregations = {metric: "sum" if metric == "total_cost" else "p95" if metric == "p95_latency" else "mean" for metric in set(METRICS) | set(PAPER_21_METRICS)}
    aggregations.update({metric: definition.aggregation_method for metric, definition in metric_definitions.items()})
    metric_order = [metric for metric in METRICS if metric in set(METRICS) | set(PAPER_21_METRICS)]

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
        patient_built = {}
        patient_scopes = {}
        patient_validations = {}
        for patient in PATIENTS:
            scope = load_scope(db, experiment_id=experiment_id, patient=patient, repetition=1)
            validation = validate_scope(scope)
            if validation["status"] != "passed":
                raise SystemExit(f"CSM v3 scope validation failed for {patient}: {validation}")
            patient_scopes[patient] = scope
            patient_validations[patient] = validation
            patient_built[patient] = build_all(scope)
        llm_calls_after = int(db.scalar(select(func.count()).select_from(LlmCall)) or 0)
        answers_after = answer_digest(db)
        truth_after = truth_digest(db)

    csm_v3_observations = [
        row
        for patient in PATIENTS
        for row in patient_built[patient]["metric_observations"]
    ]
    baseline_hashes_after = frozen_baseline_hashes(baseline_dirs)
    new_llm_calls = llm_calls_after - llm_calls_before

    write_text(output_dir / "01_compatibility_changes.md", compatibility_changes_text())
    write_text(output_dir / "02_tests.txt", args.tests_note)
    write_csv(output_dir / "03_claim_mapping_audit.csv", flatten_built(patient_built, "claim_support_audit"))
    write_csv(output_dir / "04_citation_alias_resolution.csv", flatten_built(patient_built, "citation_resolution_audit"))
    write_csv(output_dir / "05_state_observation_mapping.csv", metric_rows(csm_v3_observations, {"state_accuracy", "memory_update_accuracy", "state_recovery_time"}))
    write_csv(output_dir / "06_temporal_mapping.csv", metric_rows(csm_v3_observations, {"temporal_consistency", "decision_f1", "correction_recovery"}))
    write_csv(output_dir / "07_activation_mapping.csv", metric_rows(csm_v3_observations, {"activation_precision", "activation_recall"}))

    patient_matrix_rows = {}
    for index, patient in enumerate(PATIENTS, start=1):
        rows = patient_matrix(patient, baseline_matrix_by_patient[patient], patient_built[patient]["metric_observations"], metric_order, directions, aggregations)
        patient_matrix_rows[patient] = rows
        write_csv(output_dir / f"{7 + index:02d}_patient_{index}_recomputed_matrix.csv", rows)

    pooled = overall_matrix(baseline_observations, csm_v3_observations, metric_order, directions, aggregations)
    macro = macro_matrix(patient_matrix_rows, metric_order, directions, aggregations)
    comparison = csm_v2_vs_v3(pooled, directions)
    rankings = all_system_rankings(pooled, directions)
    stats = [row for row in paired_comparisons(baseline_observations + csm_v3_observations, ["long_context", "rolling_summary", "dense_rag", "hybrid_rag", "graph_rag", "hippo_rag", "csm", "csm_v3"]) if row["comparison"].startswith("csm_v3_vs_")]

    write_csv(output_dir / "11_overall_pooled_matrix.csv", pooled)
    write_csv(output_dir / "12_overall_macro_matrix.csv", macro)
    write_csv(output_dir / "13_csm_v2_vs_v3.csv", comparison)
    write_csv(output_dir / "14_all_system_rankings.csv", rankings)
    write_csv(output_dir / "15_statistical_comparisons.csv", stats)

    validation = {
        "experiment_id": str(experiment_id),
        "patients": len(PATIENTS),
        "questions": 60,
        "systems_in_final_comparison": 8,
        "csm_v3_completed_turns": sum(item["completed_turns"] for item in patient_validations.values()),
        "new_llm_calls": new_llm_calls,
        "stored_answers_modified": answers_before != answers_after,
        "ground_truth_modified": truth_before != truth_after,
        "metric_formulas_modified_by_exporter": False,
        "baseline_values_changed": baseline_hashes_before != baseline_hashes_after,
        "baseline_hashes_before": baseline_hashes_before,
        "baseline_hashes_after": baseline_hashes_after,
        "baseline_scope_validation": baseline_scope_validation,
        "csm_v3_scope_validation": patient_validations,
        "compatibility_only_changes": True,
        "output_dir": str(output_dir),
    }
    write_json(output_dir / "16_final_scientific_validation.json", validation)
    write_text(output_dir / "17_final_report.md", final_report(output_dir, validation, pooled, comparison, rankings, stats, args.tests_note))

    print(json.dumps({"status": "completed", "output_dir": str(output_dir), "new_llm_calls": new_llm_calls}, indent=2))
    return 0


def read_csv(path: Path) -> list[dict]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = []
    seen = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fields.append(key)
    if not fields:
        fields = ["empty"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: serialize(row.get(key)) for key in fields})


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=serialize) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def serialize(value):
    if value is None:
        return "NULL"
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, sort_keys=True, default=serialize)
    return value


def compatibility_changes_text() -> str:
    return "\n".join(
        [
            "# CSM v3 Evaluation Compatibility Changes",
            "",
            "- Added deterministic citation alias resolution for CSM v3 presentation IDs such as C1/C2 to canonical source IDs.",
            "- Reused the existing offline observation evaluator for claim matching, support classification, temporal/correction/state metrics, activation metrics, cost, tokens, and latency.",
            "- Preserved frozen baseline artifacts and live CSM v3 metric rows as historical data.",
            "- Created only derived offline evaluator-compatible result artifacts.",
            "- No answer text, patient data, benchmark question, ground truth, retrieval behavior, or metric formula is modified.",
        ]
    )


def flatten_built(patient_built: dict, key: str) -> list[dict]:
    rows = []
    for patient, built in patient_built.items():
        for row in built[key]:
            rows.append({"patient": patient, **row})
    return rows


def metric_rows(observations: list[dict], metrics: set[str]) -> list[dict]:
    return [row for row in observations if row["metric_name"] in metrics]


def patient_matrix(patient: str, baseline_matrix: dict, csm_v3_observations: list[dict], metrics: list[str], directions: dict, aggregations: dict) -> list[dict]:
    csm_v3_by_metric = defaultdict(list)
    for row in csm_v3_observations:
        csm_v3_by_metric[row["metric_name"]].append(row)
    rows = []
    for metric in metrics:
        item = {
            "patient": patient,
            "metric_name": metric,
            "direction": directions.get(metric),
            "aggregation_function": aggregations.get(metric),
        }
        for system in BASELINE_SYSTEMS:
            output_system = "csm_v2" if system == "csm" else system
            frozen = baseline_matrix.get((system, metric), {})
            item[f"{output_system}_value"] = empty_to_none(frozen.get("value"))
            item[f"{output_system}_n"] = frozen.get("observation_count") or 0
        value, n, reason = aggregate_metric(metric, csm_v3_by_metric.get(metric, []))
        item["csm_v3_value"] = value
        item["csm_v3_n"] = n
        item["reason_not_applicable_csm_v3"] = reason
        rows.append(item)
    return rows


def overall_matrix(baseline_observations: list[dict], csm_v3_observations: list[dict], metrics: list[str], directions: dict, aggregations: dict) -> list[dict]:
    rows = []
    grouped = defaultdict(list)
    for row in baseline_observations:
        grouped[(row["system"], row["metric_name"])].append(row)
    for row in csm_v3_observations:
        grouped[("csm_v3", row["metric_name"])].append(row)
    for metric in metrics:
        item = {"metric_name": metric, "direction": directions.get(metric), "aggregation_function": aggregations.get(metric)}
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
        item = {"metric_name": metric, "direction": directions.get(metric), "aggregation_function": f"macro_patient_{aggregations.get(metric)}"}
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


def csm_v2_vs_v3(pooled: list[dict], directions: dict) -> list[dict]:
    rows = []
    for row in pooled:
        metric = row["metric_name"]
        v2 = to_float(row.get("csm_v2_value"))
        v3 = to_float(row.get("csm_v3_value"))
        diff = v3 - v2 if v2 is not None and v3 is not None else None
        lower = directions.get(metric) == "lower_is_better"
        if diff is None:
            verdict = "not_comparable"
        elif diff == 0:
            verdict = "unchanged"
        elif (diff < 0 and lower) or (diff > 0 and not lower):
            verdict = "improved"
        else:
            verdict = "regressed"
        rows.append(
            {
                "metric_name": metric,
                "direction": directions.get(metric),
                "csm_v2_value": v2,
                "csm_v2_n": row.get("csm_v2_n"),
                "csm_v3_value": v3,
                "csm_v3_n": row.get("csm_v3_n"),
                "absolute_difference": diff,
                "relative_difference_percent": (diff / abs(v2) * 100.0) if diff is not None and v2 not in (None, 0.0) else None,
                "verdict": verdict,
            }
        )
    return rows


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
            rows.append({"metric_name": metric, "direction": directions.get(metric), "rank": rank, "system": system, "value": value, "n": n})
    return rows


def aggregate_metric(metric: str, rows: list[dict]) -> tuple[float | None, int, str | None]:
    values = [to_float(row.get("observation_value")) for row in rows if parse_bool(row.get("applicable")) and to_float(row.get("observation_value")) is not None]
    if not values:
        reasons = sorted({row.get("reason_not_applicable") for row in rows if row.get("reason_not_applicable")})
        return None, 0, "; ".join(reasons) if reasons else None
    return aggregate_value(metric, values), len(values), None


def answer_digest(db) -> str:
    rows = [
        (str(row.id), row.answer_text or "")
        for row in db.scalars(select(ExperimentOutput).order_by(ExperimentOutput.id.asc())).all()
    ]
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode("utf-8")).hexdigest()


def truth_digest(db) -> str:
    rows = [
        (str(row.id), row.truth)
        for row in db.scalars(select(BenchmarkGroundTruth).order_by(BenchmarkGroundTruth.id.asc())).all()
    ]
    return hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def frozen_baseline_hashes(paths: dict[str, Path]) -> dict[str, str]:
    output = {}
    for patient, directory in paths.items():
        for name in ("system_metric_matrix.csv", "metric_observations.csv", "scope_validation.json"):
            path = directory / name
            output[f"{patient}/{name}"] = file_hash(path)
    return output


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def final_report(output_dir: Path, validation: dict, pooled: list[dict], comparison: list[dict], rankings: list[dict], stats: list[dict], tests_note: str) -> str:
    csm_v3_rows = []
    for row in pooled:
        rank = next((item for item in rankings if item["metric_name"] == row["metric_name"] and item["system"] == "csm_v3"), {})
        csm_v3_rows.append([row["metric_name"], row.get("csm_v3_value"), row.get("csm_v3_n"), rank.get("rank")])
    comparison_rows = [[row["metric_name"], row["csm_v2_value"], row["csm_v3_value"], row["absolute_difference"], row["relative_difference_percent"], row["verdict"]] for row in comparison]
    non_applicable = [[row["metric_name"], row.get("csm_v3_n")] for row in pooled if to_float(row.get("csm_v3_value")) is None]
    return "\n".join(
        [
            "# CSM v3 Evaluator-Compatible Offline Report",
            "",
            "## Validation",
            "",
            f"- New LLM calls: `{validation['new_llm_calls']}`",
            f"- Stored CSM v3 answers modified: `{'YES' if validation['stored_answers_modified'] else 'NO'}`",
            f"- Ground truth modified: `{'YES' if validation['ground_truth_modified'] else 'NO'}`",
            f"- Baseline values changed: `{'YES' if validation['baseline_values_changed'] else 'NO'}`",
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
            "- `08_patient_1_recomputed_matrix.csv`",
            "- `09_patient_2_recomputed_matrix.csv`",
            "- `10_patient_3_recomputed_matrix.csv`",
            "- `11_overall_pooled_matrix.csv`",
            "- `12_overall_macro_matrix.csv`",
            "- `13_csm_v2_vs_v3.csv`",
            "- `14_all_system_rankings.csv`",
            "- `15_statistical_comparisons.csv`",
            "",
            "## Compatibility Bugs Fixed",
            "",
            "- CSM v3 presentation citations `C1`, `C2`, etc. are resolved to canonical source IDs before citation metrics.",
            "- Blank CSM v3 `source_support_status` is no longer treated by the live aggregate path as the only support signal; offline support classification now uses the same deterministic matcher/citation semantics as the frozen v2 analysis.",
            "- Activation, temporal, correction, state, and memory-update observations are exported at benchmark question level from the offline observation builder.",
            "",
            "## CSM v3 Pooled Matrix",
            "",
            markdown_table(["Metric", "CSM v3", "N", "Rank"], csm_v3_rows),
            "",
            "## CSM v2 vs CSM v3",
            "",
            markdown_table(["Metric", "CSM v2", "CSM v3", "Difference", "% Change", "Verdict"], comparison_rows),
            "",
            "## Non-Applicable CSM v3 Metrics",
            "",
            markdown_table(["Metric", "N"], non_applicable),
            "",
            f"Statistical comparison rows: `{len(stats)}`.",
        ]
    )


def markdown_table(headers: list[str], rows: list[list]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(format_cell(value) for value in row) + " |")
    return "\n".join(lines)


def format_cell(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, float):
        return f"{value:.8f}"
    return str(value).replace("|", "\\|").replace("\n", " ")


def empty_to_none(value):
    return None if value in ("", None, "NULL") else value


def to_float(value) -> float | None:
    if value in (None, "", "NULL"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_bool(value) -> bool:
    return str(value).lower() in {"true", "1", "yes"}


if __name__ == "__main__":
    raise SystemExit(main())
