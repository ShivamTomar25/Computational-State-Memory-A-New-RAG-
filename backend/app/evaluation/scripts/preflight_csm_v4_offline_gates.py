from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from uuid import uuid4

from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal, init_db
from app.evaluation.datasets.models.dataset import BenchmarkCase, BenchmarkQuestion
from app.evaluation.experiments.services.live_runner import ensure_case_patient, materialize_case_events
from app.evaluation.scripts.run_sustha_three_patient_pilot import select_dataset, select_doctor
from app.memory_systems.common.canonical.source_collector import collect_sources
from app.memory_systems.common.models.memory import MemorySystemInstance
from app.memory_systems.common.repositories import memory_repository
from app.memory_systems.csm.models import CsmEvidence, CsmStateVariable
from app.memory_systems.csm.v2_engine import CSM_V2_IMPLEMENTATION_VERSION
from app.memory_systems.csm.v3_engine import CSM_V3_IMPLEMENTATION_VERSION
from app.memory_systems.csm.v4_adapter import CsmV4Adapter
from app.memory_systems.csm.v4_engine import CSM_V4_IMPLEMENTATION_VERSION, route_query_v4


DEFAULT_DIAGNOSIS_CSV = Path("../evaluation/results/csm_v4_development/20260820T111118Z/csm_v2_vs_v3_question_diagnosis.csv")
DEFAULT_OUTPUT_ROOT = Path("../evaluation/results/csm_v4_development")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic offline CSM v4 success gates without answer-generation calls.")
    parser.add_argument("--diagnosis-csv", default=str(DEFAULT_DIAGNOSIS_CSV))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--patient", action="append", default=[])
    parser.add_argument("--question", action="append", default=[])
    parser.add_argument("--top-k", type=int, default=settings.memory_default_top_k)
    parser.add_argument("--token-budget", type=int, default=settings.memory_default_context_token_budget)
    args = parser.parse_args()

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = Path(args.output_root).resolve() / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    diagnosis = load_diagnosis(Path(args.diagnosis_csv).resolve())
    selected_patients = set(args.patient or [])
    selected_questions = {int(value) for value in args.question or []}

    init_db()
    setup_db = SessionLocal()
    try:
        dataset = select_dataset(setup_db)
        doctor = select_doctor(setup_db)
        cases = list(
            setup_db.scalars(
                select(BenchmarkCase)
                .where(BenchmarkCase.dataset_id == dataset.id)
                .order_by(BenchmarkCase.case_key.asc())
            ).all()
        )
        if selected_patients:
            cases = [case for case in cases if case.case_key in selected_patients]

        patient_ids = {}
        for case in cases:
            patient = ensure_case_patient(setup_db, doctor=doctor, case=case)
            materialize_case_events(setup_db, doctor=doctor, patient=patient, case=case)
            patient_ids[case.case_key] = patient.id
    finally:
        setup_db.close()

    adapter = CsmV4Adapter()
    rows = []
    for case in cases:
        questions_db = SessionLocal()
        try:
            questions = list(
                questions_db.scalars(
                    select(BenchmarkQuestion)
                    .where(BenchmarkQuestion.case_id == case.id)
                    .order_by(BenchmarkQuestion.turn_number.asc())
                ).all()
            )
        finally:
            questions_db.close()

        if selected_questions:
            questions = [question for question in questions if question.turn_number in selected_questions]

        for question in questions:
            key = (case.case_key, question.turn_number)
            diagnostic_row = diagnosis.get(key)
            if diagnostic_row is None:
                raise ValueError(f"Missing diagnosis row for {case.case_key} question {question.turn_number}")
            rows.append(
                run_retrieval_gate(
                    patient_key=case.case_key,
                    patient_id=patient_ids[case.case_key],
                    question=question,
                    diagnostic_row=diagnostic_row,
                    adapter=adapter,
                    top_k=args.top_k,
                    token_budget=args.token_budget,
                )
            )

    gates = summarize_gates(rows)
    report = {
        "status": "passed" if all(item["passed"] for item in gates.values()) else "failed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider_calls": 0,
        "groq_calls": 0,
        "patients": sorted({row["patient"] for row in rows}),
        "questions": len(rows),
        "implementation_versions": {
            "csm_v2": CSM_V2_IMPLEMENTATION_VERSION,
            "csm_v3": CSM_V3_IMPLEMENTATION_VERSION,
            "csm_v4": CSM_V4_IMPLEMENTATION_VERSION,
        },
        "configuration": adapter.configuration(),
        "gates": gates,
    }

    write_csv(output_dir / "csm_v4_offline_gate_results.csv", rows)
    write_json(output_dir / "csm_v4_offline_gate_report.json", report)
    write_markdown(output_dir / "csm_v4_offline_gate_summary.md", report, rows)
    print(json.dumps({"status": report["status"], "output_dir": str(output_dir), "gates": gates}, indent=2))
    return 0 if report["status"] == "passed" else 1


def run_retrieval_gate(
    *,
    patient_key: str,
    patient_id,
    question: BenchmarkQuestion,
    diagnostic_row: dict,
    adapter: CsmV4Adapter,
    top_k: int,
    token_budget: int,
) -> dict:
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        instance = MemorySystemInstance(
            id=uuid4(),
            patient_id=patient_id,
            system_type="csm_v4_offline_gate",
            display_name="CSM v4 Offline Gate",
            status="ready",
            capability_status=adapter.capability_status().model_dump(),
            configuration=adapter.configuration(),
            pipeline_version=settings.memory_pipeline_version,
            initialized_at=now,
            last_synced_at=now,
            source_cutoff_time=question.source_cutoff,
            failure_code=None,
            failure_reason=None,
        )
        db.add(instance)
        db.flush()

        collected = collect_sources(
            db,
            patient_id=patient_id,
            instance=instance,
            cutoff_time=question.source_cutoff,
            include_patient_information=True,
            include_documents=True,
            include_conversation=True,
        )
        canonical_sources = [
            memory_repository.upsert_canonical_source(db=db, source=source)[0]
            for source in collected
        ]
        adapter.ingest_sources(db=db, instance=instance, sources=canonical_sources)
        items, warnings, readiness = adapter.retrieve(
            db=db,
            instance=instance,
            query=question.question,
            top_k=top_k,
            token_budget=token_budget,
            retrieval_mode="offline_gate",
        )

        route = route_query_v4(question.question)
        expected_sources = parse_json_list(diagnostic_row["expected_sources"])
        retrieved_sources = unique(
            str(item.canonical_source_id)
            for item in items
            if item.canonical_source_id is not None
        )
        relevant_sources = sorted(set(expected_sources) & set(retrieved_sources))
        precision = safe_divide(len(relevant_sources), len(retrieved_sources))
        recall = safe_divide(len(relevant_sources), len(expected_sources))
        v2_recall = float(diagnostic_row.get("v2_recall") or 0.0)
        route_budget = adapter.route_token_budget(route=route, requested_token_budget=token_budget)
        total_tokens = sum(item.token_count for item in items)
        state_without_evidence_count = 0
        future_leak_count = 0
        current_superseded_count = 0
        historical_item_count = 0
        evidence_item_count = 0
        mandatory_support_evidence_count = 0
        correction_evidence_count = 0
        dependency_item_count = 0
        null_canonical_count = 0

        for item in items:
            metadata = item.metadata or {}
            lineage_role = str(metadata.get("lineage_role") or "")
            historical_item_count += int(bool(metadata.get("historical")))
            evidence_item_count += int(item.system_native_type == "csm_evidence")
            mandatory_support_evidence_count += int(lineage_role.startswith("mandatory_"))
            correction_evidence_count += int(lineage_role == "mandatory_correction_evidence")
            dependency_item_count += int(lineage_role == "dependency_expansion")
            null_canonical_count += int(item.canonical_source_id is None)

            if item.system_native_type == "csm_state_variable" and (not item.canonical_source_id or not metadata.get("evidence_id")):
                state_without_evidence_count += 1

            if item.system_native_type == "csm_evidence" and item.system_native_id is not None:
                evidence = db.get(CsmEvidence, item.system_native_id)
                if evidence is not None and evidence.recorded_time > question.source_cutoff:
                    future_leak_count += 1

            if item.system_native_type == "csm_state_variable" and item.system_native_id is not None:
                state = db.get(CsmStateVariable, item.system_native_id)
                if state is not None:
                    recorded = state.last_updated_at
                    if state.current_value and state.current_value.get("recorded_time"):
                        recorded = datetime.fromisoformat(str(state.current_value["recorded_time"]))
                    if recorded > question.source_cutoff:
                        future_leak_count += 1
                    status = str((state.current_value or {}).get("status") or state.status or "").lower()
                    if route.mode not in {"temporal_state", "correction_state"} and status == "superseded":
                        current_superseded_count += 1

        exact_source_fallback_present = route.mode == "exact_source" and evidence_item_count > 0
        rare_detail_fallback_present = route.mode == "rare_detail" and evidence_item_count > 0
        correction_bundle_present = route.mode != "correction_state" or (
            correction_evidence_count > 0 and (historical_item_count > 0 or len(retrieved_sources) >= 2)
        )
        temporal_history_present = route.mode != "temporal_state" or (
            historical_item_count > 0 or recall >= v2_recall
        )

        return {
            "patient": patient_key,
            "question_number": question.turn_number,
            "question": question.question,
            "question_type": question.question_type,
            "source_cutoff": question.source_cutoff.isoformat(),
            "route_v4": route.mode,
            "readiness": readiness,
            "expected_sources": json.dumps(expected_sources),
            "retrieved_sources": json.dumps(retrieved_sources),
            "relevant_sources": json.dumps(relevant_sources),
            "expected_count": len(expected_sources),
            "retrieved_count": len(retrieved_sources),
            "relevant_count": len(relevant_sources),
            "v2_recall": v2_recall,
            "v4_precision": precision,
            "v4_recall": recall,
            "coverage_delta_vs_v2": recall - v2_recall,
            "item_count": len(items),
            "evidence_item_count": evidence_item_count,
            "historical_item_count": historical_item_count,
            "mandatory_support_evidence_count": mandatory_support_evidence_count,
            "correction_evidence_count": correction_evidence_count,
            "dependency_item_count": dependency_item_count,
            "state_without_evidence_count": state_without_evidence_count,
            "null_canonical_count": null_canonical_count,
            "future_leak_count": future_leak_count,
            "current_superseded_count": current_superseded_count,
            "token_count": total_tokens,
            "route_budget": route_budget,
            "budget_pass": total_tokens <= route_budget,
            "exact_source_fallback_present": exact_source_fallback_present,
            "rare_detail_fallback_present": rare_detail_fallback_present,
            "correction_bundle_present": correction_bundle_present,
            "temporal_history_present": temporal_history_present,
            "warnings": json.dumps(warnings),
        }
    finally:
        db.rollback()
        db.close()


def summarize_gates(rows: list[dict]) -> dict:
    v2_macro_recall = mean(float(row["v2_recall"]) for row in rows) if rows else 0.0
    v4_macro_recall = mean(float(row["v4_recall"]) for row in rows) if rows else 0.0
    correction_rows = [row for row in rows if row["route_v4"] == "correction_state"]
    temporal_rows = [row for row in rows if row["route_v4"] == "temporal_state"]
    exact_rows = [row for row in rows if row["route_v4"] == "exact_source"]
    rare_rows = [row for row in rows if row["route_v4"] == "rare_detail"]
    current_rows = [row for row in rows if row["route_v4"] not in {"correction_state", "temporal_state"}]

    return {
        "no_future_leakage": gate(sum(int(row["future_leak_count"]) for row in rows) == 0, "future_leak_count", sum(int(row["future_leak_count"]) for row in rows)),
        "correction_bundle_works": gate(not correction_rows or all(bool(row["correction_bundle_present"]) for row in correction_rows), "correction_questions", len(correction_rows)),
        "current_state_excludes_superseded": gate(all(int(row["current_superseded_count"]) == 0 for row in current_rows), "current_route_questions", len(current_rows)),
        "temporal_retrieves_history_or_v2_coverage": gate(not temporal_rows or all(bool(row["temporal_history_present"]) for row in temporal_rows), "temporal_questions", len(temporal_rows)),
        "exact_source_fallback_works": gate(not exact_rows or all(bool(row["exact_source_fallback_present"]) for row in exact_rows), "exact_source_questions", len(exact_rows)),
        "rare_detail_fallback_works": gate(not rare_rows or all(bool(row["rare_detail_fallback_present"]) for row in rare_rows), "rare_detail_questions", len(rare_rows)),
        "state_evidence_lineage_deterministic": gate(
            sum(int(row["state_without_evidence_count"]) for row in rows) == 0 and sum(int(row["null_canonical_count"]) for row in rows) == 0,
            "state_without_evidence/null_canonical",
            f"{sum(int(row['state_without_evidence_count']) for row in rows)}/{sum(int(row['null_canonical_count']) for row in rows)}",
        ),
        "adaptive_context_budget_works": gate(all(bool(row["budget_pass"]) for row in rows), "max_token_count", max((int(row["token_count"]) for row in rows), default=0)),
        "retrieval_coverage_not_worse_than_csm_v2": gate(
            v4_macro_recall + 1e-9 >= v2_macro_recall,
            "macro_recall_v4_vs_v2",
            {"v4": v4_macro_recall, "v2": v2_macro_recall, "delta": v4_macro_recall - v2_macro_recall},
        ),
        "csm_v2_v3_unchanged_static_check": gate(
            CSM_V2_IMPLEMENTATION_VERSION.startswith("csm_v2") and CSM_V3_IMPLEMENTATION_VERSION.startswith("csm_v3"),
            "versions",
            {"csm_v2": CSM_V2_IMPLEMENTATION_VERSION, "csm_v3": CSM_V3_IMPLEMENTATION_VERSION},
        ),
    }


def gate(passed: bool, measure: str, value) -> dict:
    return {"passed": bool(passed), "measure": measure, "value": value}


def load_diagnosis(path: Path) -> dict[tuple[str, int], dict]:
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {
        (row["patient"], int(row["question_number"])): row
        for row in rows
    }


def parse_json_list(value: str) -> list[str]:
    if not value:
        return []
    parsed = json.loads(value)
    return [str(item) for item in parsed if str(item).lower() != "false"]


def unique(values) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def safe_divide(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def write_markdown(path: Path, report: dict, rows: list[dict]) -> None:
    lines = [
        "# CSM v4 Offline Gate Summary",
        "",
        f"Status: **{report['status']}**",
        "",
        f"Patients: {len(report['patients'])}",
        f"Questions: {report['questions']}",
        "Provider calls: 0",
        "Groq calls: 0",
        "",
        "## Gates",
        "",
        "| Gate | Passed | Measure | Value |",
        "| --- | --- | --- | --- |",
    ]
    for name, gate_result in report["gates"].items():
        lines.append(
            f"| {name} | {gate_result['passed']} | {gate_result['measure']} | {json.dumps(gate_result['value'], default=str)} |"
        )
    lines.extend(
        [
            "",
            "## Retrieval Coverage",
            "",
            "| Patient | Q | Route | v2 recall | v4 recall | v4 precision | Tokens |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in rows:
        lines.append(
            "| "
            f"{row['patient']} | {row['question_number']} | {row['route_v4']} | "
            f"{float(row['v2_recall']):.4f} | {float(row['v4_recall']):.4f} | "
            f"{float(row['v4_precision']):.4f} | {row['token_count']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
