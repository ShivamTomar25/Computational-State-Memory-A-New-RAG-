from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.database import SessionLocal
from app.evaluation.datasets.models.dataset import BenchmarkCase, BenchmarkQuestion
from app.evaluation.offline_recomputation.observation_builder import build_all
from app.evaluation.offline_recomputation.scope_loader import load_scope, validate_scope
from app.memory_systems.common.models.memory import MemorySystemInstance
from app.memory_systems.csm.models import CsmEvidence, CsmUpdateEvent
from app.memory_systems.csm.v2_engine import route_query as route_query_v2
from app.memory_systems.csm.v3_engine import route_query_v3
from app.patient.model import Patient


PATIENTS = ["SYN-CSM-001", "SYN-CSM-002", "SYN-CSM-003"]
BASELINE_DIRS = {
    "SYN-CSM-001": "../evaluation/results/csm_v2_final_comparison_offline_v3/SYN-CSM-001/repetition_1/20260722T115832Z",
    "SYN-CSM-002": "../evaluation/results/csm_v2_final_comparison_offline_v3/SYN-CSM-002/repetition_1/20260819T104212Z",
    "SYN-CSM-003": "../evaluation/results/csm_v2_final_comparison_offline_v3/SYN-CSM-003/repetition_1/20260819T104216Z",
}
CSM_V3_EXPERIMENT_ID = UUID("2327c728-69ec-4fc4-9410-771c225d61a0")
REQUIRED_COLUMNS = [
    "patient",
    "question_number",
    "question",
    "route_v2",
    "route_v3",
    "expected_sources",
    "v2_sources",
    "v3_sources",
    "sources_lost_in_v3",
    "sources_added_in_v3",
    "v2_precision",
    "v3_precision",
    "v2_recall",
    "v3_recall",
    "v2_answer_score",
    "v3_answer_score",
    "v2_tokens",
    "v3_tokens",
    "diagnosed_failure_reason",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate offline per-question CSM v2 vs v3 diagnosis without LLM calls.")
    parser.add_argument("--experiment-id", default=str(CSM_V3_EXPERIMENT_ID))
    parser.add_argument("--output-root", default="../evaluation/results/csm_v4_development")
    args = parser.parse_args()

    backend_dir = Path(__file__).resolve().parents[3]
    baseline_dirs = {patient: (backend_dir / relative).resolve() for patient, relative in BASELINE_DIRS.items()}
    output_dir = (backend_dir / args.output_root / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")).resolve()
    output_dir.mkdir(parents=True, exist_ok=False)

    v2 = {patient: load_v2_patient_artifacts(patient, directory) for patient, directory in baseline_dirs.items()}

    with SessionLocal() as db:
        question_text = load_questions(db)
        route_events = load_route_events(db)
        evidence_to_source = {
            str(row.id): str(row.canonical_source_id)
            for row in db.scalars(select(CsmEvidence)).all()
        }
        v3_built = {}
        v3_validations = {}
        for patient in PATIENTS:
            scope = load_scope(db, experiment_id=UUID(args.experiment_id), patient=patient, repetition=1)
            validation = validate_scope(scope)
            if validation["status"] != "passed":
                raise SystemExit(f"CSM v3 scope validation failed for {patient}: {validation}")
            v3_validations[patient] = validation
            v3_built[patient] = build_all(scope)

    rows = []
    detail_rows = []
    for patient in PATIENTS:
        v3_artifacts = build_v3_patient_artifacts(v3_built[patient])
        for question_number in range(1, 21):
            question = question_text.get((patient, question_number), "")
            v2_key = (patient, question_number)
            v3_key = (patient, question_number)
            v2_sources = v2[patient]["retrieved_sources"].get(v2_key, set())
            v3_sources = v3_artifacts["retrieved_sources"].get(v3_key, set())
            expected_sources = v2[patient]["expected_sources"].get(v2_key) or v3_artifacts["expected_sources"].get(v3_key, set())
            sources_lost = (expected_sources & v2_sources) - v3_sources
            sources_added = v3_sources - v2_sources
            v2_metrics = v2[patient]["metrics"].get(v2_key, {})
            v3_metrics = v3_artifacts["metrics"].get(v3_key, {})
            v2_route = route_events.get((patient, "csm", question), {}).get("route") or route_query_v2(question).mode
            v3_route_event = route_events.get((patient, "csm_v3", question), {})
            v3_route = v3_route_event.get("route") or route_query_v3(question).mode
            diagnosis = diagnose_failure(
                route_v2=v2_route,
                route_v3=v3_route,
                expected_sources=expected_sources,
                v2_sources=v2_sources,
                v3_sources=v3_sources,
                v2_metrics=v2_metrics,
                v3_metrics=v3_metrics,
            )
            rows.append(
                {
                    "patient": patient,
                    "question_number": question_number,
                    "question": question,
                    "route_v2": v2_route,
                    "route_v3": v3_route,
                    "expected_sources": serialize_ids(expected_sources),
                    "v2_sources": serialize_ids(v2_sources),
                    "v3_sources": serialize_ids(v3_sources),
                    "sources_lost_in_v3": serialize_ids(sources_lost),
                    "sources_added_in_v3": serialize_ids(sources_added),
                    "v2_precision": value(v2_metrics, "retrieval_precision"),
                    "v3_precision": value(v3_metrics, "retrieval_precision"),
                    "v2_recall": value(v2_metrics, "retrieval_recall"),
                    "v3_recall": value(v3_metrics, "retrieval_recall"),
                    "v2_answer_score": value(v2_metrics, "answer_accuracy"),
                    "v3_answer_score": value(v3_metrics, "answer_accuracy"),
                    "v2_tokens": value(v2_metrics, "tokens_per_query"),
                    "v3_tokens": value(v3_metrics, "tokens_per_query"),
                    "diagnosed_failure_reason": diagnosis,
                }
            )
            detail_rows.append(
                {
                    "patient": patient,
                    "question_number": question_number,
                    "question": question,
                    "route_v2": {
                        "mode": v2_route,
                        "source": "stored_query_route_event_or_deterministic_router_fallback",
                    },
                    "route_v3": {
                        "mode": v3_route,
                        "source": "stored_activation_audit_event_or_deterministic_router_fallback",
                        "event": v3_route_event,
                    },
                    "selected_states_v2": sorted(v2[patient]["selected_states"].get((patient, question), set())),
                    "selected_evidence_v2": sorted(v2[patient]["selected_activation_sources"].get((patient, question), set())),
                    "selected_states_v3": sorted(v3_route_event.get("state_ids_selected", [])),
                    "selected_evidence_v3": sorted(
                        evidence_to_source.get(evidence_id, evidence_id)
                        for evidence_id in v3_route_event.get("supporting_evidence_ids", [])
                    ),
                    "expected_sources": sorted(expected_sources),
                    "retrieved_sources_v2": sorted(v2_sources),
                    "retrieved_sources_v3": sorted(v3_sources),
                    "sources_lost_in_v3": sorted(sources_lost),
                    "sources_added_in_v3": sorted(sources_added),
                    "citations_v2": v2[patient]["citations"].get(v2_key, []),
                    "citations_v3": v3_artifacts["citations"].get(v3_key, []),
                    "claims_v2": v2[patient]["claims"].get(v2_key, []),
                    "claims_v3": v3_artifacts["claims"].get(v3_key, []),
                    "metrics_v2": v2_metrics,
                    "metrics_v3": v3_metrics,
                    "diagnosed_failure_reason": diagnosis,
                    "candidate_persistence_note": "v3 stores activation candidate counts/components in CsmUpdateEvent; v2 frozen artifacts store selected activation rows but not every candidate considered.",
                }
            )

    write_csv(output_dir / "csm_v2_vs_v3_question_diagnosis.csv", rows, REQUIRED_COLUMNS)
    write_json(output_dir / "csm_v2_vs_v3_question_diagnosis_details.json", detail_rows)
    write_text(output_dir / "csm_v2_vs_v3_failure_summary.md", failure_summary(rows, v3_validations))
    write_json(
        output_dir / "diagnosis_manifest.json",
        {
            "status": "completed",
            "new_llm_calls": 0,
            "patients": len(PATIENTS),
            "questions": len(rows),
            "csm_v3_experiment_id": str(args.experiment_id),
            "baseline_dirs": {patient: str(directory) for patient, directory in baseline_dirs.items()},
            "output_dir": str(output_dir),
        },
    )
    print(json.dumps({"status": "completed", "output_dir": str(output_dir), "rows": len(rows), "new_llm_calls": 0}, indent=2))
    return 0


def load_v2_patient_artifacts(patient: str, directory: Path) -> dict[str, Any]:
    per_question = read_csv(directory / "per_question_results.csv")
    retrieval = read_csv(directory / "retrieval_identifier_resolution_audit.csv")
    activation = read_csv(directory / "csm_activation_audit.csv")
    citations = read_csv(directory / "citation_resolution_audit.csv")
    claims = read_csv(directory / "claim_support_audit.csv")
    return {
        "metrics": {
            (row["patient"], int(row["question_number"])): row
            for row in per_question
            if row.get("system") == "csm"
        },
        "expected_sources": expected_sources_by_question(retrieval, system="csm"),
        "retrieved_sources": retrieved_sources_by_question(retrieval, system="csm"),
        "selected_states": selected_states_by_query(patient, activation),
        "selected_activation_sources": selected_sources_by_query(patient, activation),
        "citations": grouped_rows(citations, system="csm"),
        "claims": grouped_rows(claims, system="csm"),
    }


def build_v3_patient_artifacts(built: dict[str, Any]) -> dict[str, Any]:
    observations = built["metric_observations"]
    metrics = defaultdict(dict)
    for row in observations:
        if row["system"] != "csm_v3":
            continue
        metrics[(row["patient"], int(row["question_number"]))][row["metric_name"]] = row["observation_value"]
    retrieval = built["retrieval_identifier_resolution_audit"]
    return {
        "metrics": dict(metrics),
        "expected_sources": expected_sources_by_question(retrieval, system="csm_v3"),
        "retrieved_sources": retrieved_sources_by_question(retrieval, system="csm_v3"),
        "citations": grouped_rows(built["citation_resolution_audit"], system="csm_v3"),
        "claims": grouped_rows(built["claim_support_audit"], system="csm_v3"),
    }


def expected_sources_by_question(rows: list[dict], *, system: str) -> dict[tuple[str, int], set[str]]:
    grouped: dict[tuple[str, int], set[str]] = defaultdict(set)
    for row in rows:
        if row.get("system") != system:
            continue
        key = (row["patient"], int(row["question_number"]))
        grouped[key].update(parse_id_list(row.get("expected_canonical_ids")))
    return grouped


def retrieved_sources_by_question(rows: list[dict], *, system: str) -> dict[tuple[str, int], set[str]]:
    grouped: dict[tuple[str, int], set[str]] = defaultdict(set)
    for row in rows:
        if row.get("system") != system:
            continue
        key = (row["patient"], int(row["question_number"]))
        grouped[key].update(parse_id_list(row.get("resolved_canonical_ids")))
        if row.get("canonical_source_id"):
            grouped[key].add(str(row["canonical_source_id"]))
    return grouped


def selected_states_by_query(patient: str, rows: list[dict]) -> dict[tuple[str, str], set[str]]:
    grouped: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in rows:
        if parse_bool(row.get("selected")):
            grouped[(patient, row.get("query_text") or "")].add(row.get("state_variable_id") or "")
    return grouped


def selected_sources_by_query(patient: str, rows: list[dict]) -> dict[tuple[str, str], set[str]]:
    grouped: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in rows:
        if parse_bool(row.get("selected")):
            grouped[(patient, row.get("query_text") or "")].update(parse_id_list(row.get("linked_canonical_source_ids")))
    return grouped


def grouped_rows(rows: list[dict], *, system: str) -> dict[tuple[str, int], list[dict]]:
    grouped: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for row in rows:
        if row.get("system") == system:
            grouped[(row["patient"], int(row["question_number"]))].append(row)
    return grouped


def load_questions(db) -> dict[tuple[str, int], str]:
    rows = db.execute(
        select(BenchmarkCase.case_key, BenchmarkQuestion.turn_number, BenchmarkQuestion.question)
        .join(BenchmarkQuestion, BenchmarkQuestion.case_id == BenchmarkCase.id)
        .where(BenchmarkCase.case_key.in_(PATIENTS))
    ).all()
    return {(case_key, int(turn_number)): question for case_key, turn_number, question in rows}


def load_route_events(db) -> dict[tuple[str, str, str], dict]:
    rows = db.execute(
        select(
            Patient.patient_code,
            MemorySystemInstance.system_type,
            CsmUpdateEvent.event_type,
            CsmUpdateEvent.input_snapshot,
            CsmUpdateEvent.output_snapshot,
            CsmUpdateEvent.created_at,
        )
        .join(MemorySystemInstance, CsmUpdateEvent.system_instance_id == MemorySystemInstance.id)
        .join(Patient, MemorySystemInstance.patient_id == Patient.id)
        .where(
            Patient.patient_code.in_(PATIENTS),
            MemorySystemInstance.system_type.in_(["csm", "csm_v3"]),
            CsmUpdateEvent.event_type.in_(["query_route", "activation_audit"]),
        )
        .order_by(CsmUpdateEvent.created_at.asc())
    ).all()
    output = {}
    for patient, system, event_type, input_snapshot, output_snapshot, _created_at in rows:
        query = (input_snapshot or {}).get("query")
        if not query:
            continue
        snapshot = output_snapshot or {}
        route = snapshot.get("mode") or snapshot.get("route")
        output[(patient, system, query)] = {
            "event_type": event_type,
            "route": route,
            "route_reason": snapshot.get("reason") or snapshot.get("route_reason"),
            "route_features": snapshot.get("features") or snapshot.get("route_features"),
            "total_candidates": snapshot.get("total_candidates"),
            "valid_candidates": snapshot.get("valid_candidates"),
            "selected_state_count": snapshot.get("selected_state_count"),
            "selected_evidence_count": snapshot.get("selected_evidence_count"),
            "state_ids_selected": snapshot.get("state_ids_selected") or [],
            "state_versions_selected": snapshot.get("state_versions_selected") or [],
            "supporting_evidence_ids": snapshot.get("supporting_evidence_ids") or [],
            "discarded_candidate_count": len(snapshot.get("discarded_candidates") or []),
            "estimated_serialized_tokens": snapshot.get("estimated_serialized_tokens"),
            "source": "stored_db_event",
        }
    return output


def diagnose_failure(
    *,
    route_v2: str,
    route_v3: str,
    expected_sources: set[str],
    v2_sources: set[str],
    v3_sources: set[str],
    v2_metrics: dict,
    v3_metrics: dict,
) -> str:
    categories = []
    v2_recall = float_or_none(value(v2_metrics, "retrieval_recall"))
    v3_recall = float_or_none(value(v3_metrics, "retrieval_recall"))
    v2_precision = float_or_none(value(v2_metrics, "retrieval_precision"))
    v3_precision = float_or_none(value(v3_metrics, "retrieval_precision"))
    v2_answer = float_or_none(value(v2_metrics, "answer_accuracy"))
    v3_answer = float_or_none(value(v3_metrics, "answer_accuracy"))
    v2_support = float_or_none(value(v2_metrics, "evidence_support_rate"))
    v3_support = float_or_none(value(v3_metrics, "evidence_support_rate"))
    v2_temporal = float_or_none(value(v2_metrics, "temporal_consistency"))
    v3_temporal = float_or_none(value(v3_metrics, "temporal_consistency"))
    v2_correction = float_or_none(value(v2_metrics, "correction_recovery"))
    v3_correction = float_or_none(value(v3_metrics, "correction_recovery"))
    v2_memory = float_or_none(value(v2_metrics, "memory_update_accuracy"))
    v3_memory = float_or_none(value(v3_metrics, "memory_update_accuracy"))
    lost_expected = (expected_sources & v2_sources) - v3_sources

    if route_v2 != route_v3 and lower(v3_answer) < lower(v2_answer):
        categories.append("ROUTE_ERROR")
    if lost_expected and lower(v3_recall) + 0.01 < lower(v2_recall):
        categories.append("OVER_PRUNING")
    if route_v3 in {"exact_source", "rare_detail", "evidence_first"} and lost_expected:
        categories.append("MISSING_EVIDENCE_FALLBACK")
    if lower(v3_precision) < lower(v2_precision) and lower(v3_recall) < lower(v2_recall):
        categories.append("INSUFFICIENT_LINEAGE")
    if lower(v3_temporal) < lower(v2_temporal):
        categories.append("TEMPORAL_ERROR")
    if lower(v3_correction) < lower(v2_correction):
        categories.append("CORRECTION_ERROR")
    if lower(v3_memory) < lower(v2_memory):
        categories.append("STATE_UPDATE_ERROR")
    if lower(v3_answer) < lower(v2_answer) and lower(v3_support) < lower(v2_support):
        categories.append("SERIALIZATION_INFORMATION_LOSS")
    if not categories and lower(v3_answer) >= lower(v2_answer) and lower(v3_recall) >= lower(v2_recall):
        categories.append("NO_REGRESSION_DETECTED")
    elif not categories:
        categories.append("OTHER")
    detail = (
        f"lost_expected={len(lost_expected)}; "
        f"v2_recall={format_optional(v2_recall)}; v3_recall={format_optional(v3_recall)}; "
        f"v2_answer={format_optional(v2_answer)}; v3_answer={format_optional(v3_answer)}"
    )
    return "|".join(dict.fromkeys(categories)) + f": {detail}"


def failure_summary(rows: list[dict], validations: dict[str, Any]) -> str:
    counts = defaultdict(int)
    for row in rows:
        for category in row["diagnosed_failure_reason"].split(":", 1)[0].split("|"):
            counts[category] += 1
    lines = [
        "# CSM v2 vs CSM v3 Per-Question Diagnosis",
        "",
        "This is an offline forensic analysis. It uses stored CSM v2 artifacts and stored CSM v3 experiment rows only.",
        "",
        "## Validation",
        "",
        "- New LLM calls: `0`",
        f"- Patients: `{len(PATIENTS)}`",
        f"- Questions: `{len(rows)}`",
        f"- CSM v3 completed turns: `{sum(item['completed_turns'] for item in validations.values())}`",
        "",
        "## Failure Categories",
        "",
    ]
    for category, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- `{category}`: {count}")
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- CSM v3 route/candidate counts come from persisted `activation_audit` events when available.",
            "- CSM v2 route values come from persisted `query_route` events when available, otherwise the deterministic v2 router is replayed over the stored question text.",
            "- CSM v2 selected candidate details are limited to the frozen activation audit rows; discarded candidates were not exported in the v2 offline artifacts.",
        ]
    )
    return "\n".join(lines)


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def parse_id_list(value: Any) -> set[str]:
    if value in (None, "", "NULL"):
        return set()
    if isinstance(value, list):
        return {str(item) for item in value if item not in (None, "", "False", False)}
    if isinstance(value, set):
        return {str(item) for item in value if item not in (None, "", "False", False)}
    text = str(value)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = [text]
    if isinstance(parsed, str):
        parsed = [parsed]
    return {str(item) for item in parsed if item not in (None, "", "False", False)}


def serialize_ids(values: set[str]) -> str:
    return json.dumps(sorted(values))


def value(metrics: dict, key: str) -> Any:
    return metrics.get(key) if metrics else None


def lower(value_: float | None) -> float:
    return value_ if value_ is not None else -1.0


def float_or_none(value_: Any) -> float | None:
    if value_ in (None, "", "NULL"):
        return None
    try:
        return float(value_)
    except (TypeError, ValueError):
        return None


def format_optional(value_: float | None) -> str:
    return "NULL" if value_ is None else f"{value_:.6f}"


def parse_bool(value_: Any) -> bool:
    return str(value_).lower() in {"true", "1", "yes"}


if __name__ == "__main__":
    raise SystemExit(main())
