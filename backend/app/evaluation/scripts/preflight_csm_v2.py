from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

from sqlalchemy import select

from app.database import SessionLocal, init_db
from app.evaluation.datasets.models.dataset import BenchmarkCase, BenchmarkQuestion
from app.evaluation.experiments.models.experiment import ExperimentOutput, ExperimentSystemRun, ExperimentTurn
from app.evaluation.experiments.repositories import experiment_repository
from app.memory_systems.common.enums.status import SYSTEM_TYPES
from app.memory_systems.common.models.memory import MemorySystemInstance
from app.memory_systems.csm.models import CsmEvidence, CsmStateDependency, CsmStateEvidenceLink, CsmStateHistory, CsmStateVariable
from app.memory_systems.csm.v2_engine import (
    CSM_V2_IMPLEMENTATION_VERSION,
    CSM_V2_STATE_SCHEMA_VERSION,
    build_state_value_payload,
    route_query,
    should_supersede,
)
from app.patient.model import Patient


CSM_V2_COMPARISON_SYSTEM_TYPES = tuple(system for system in SYSTEM_TYPES if system not in {"csm_v3", "csm_v4"})


def main() -> int:
    parser = argparse.ArgumentParser(description="Run offline CSM v2 preflight checks without LLM/provider calls.")
    parser.add_argument("--source-experiment-id", required=True)
    parser.add_argument("--derived-experiment-id")
    parser.add_argument("--patient", required=True)
    parser.add_argument("--repetition", type=int, required=True)
    parser.add_argument("--implementation-version", default=CSM_V2_IMPLEMENTATION_VERSION)
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
        derived = experiment_repository.get_experiment(db, UUID(args.derived_experiment_id)) if args.derived_experiment_id else None
        case = db.scalar(
            select(BenchmarkCase).where(
                BenchmarkCase.dataset_id == source.dataset_id,
                BenchmarkCase.case_key == args.patient,
            )
        )
        if case is None:
            raise SystemExit(f"Benchmark case not found: {args.patient}")

        questions = list(
            db.scalars(
                select(BenchmarkQuestion)
                .where(BenchmarkQuestion.case_id == case.id)
                .order_by(BenchmarkQuestion.turn_number.asc())
            ).all()
        )
        source_audit = audit_source_scope(db, source_id=source.id, case_id=case.id, repetition=args.repetition, expected_questions=len(questions))
        derived_audit = audit_derived_scope(db, derived_id=derived.id, case_id=case.id, repetition=args.repetition, expected_questions=len(questions)) if derived else []
        invariant_rows = source_audit + derived_audit + non_patient_one_invariant_rows()
        critical_failures = [row for row in invariant_rows if row["severity"] == "critical" and row["status"] != "passed"]

        state_rows = state_replay_rows(db, patient=case.case_key)
        dependency_rows = dependency_trace_rows(db, patient=case.case_key)
        lineage_rows = lineage_rows_for_csm(db, patient=case.case_key)

        report = {
            "status": "passed" if not critical_failures else "failed",
            "critical_failure_count": len(critical_failures),
            "source_experiment_id": str(source.id),
            "derived_experiment_id": str(derived.id) if derived else None,
            "patient": args.patient,
            "repetition": args.repetition,
            "implementation_version": args.implementation_version,
            "provider_calls": 0,
            "groq_calls": 0,
            "checks": invariant_rows,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        write_json(output_dir / "csm_v2_preflight_report.json", report)
        write_csv(output_dir / "csm_v2_invariant_audit.csv", invariant_rows)
        write_csv(output_dir / "csm_v2_state_replay_audit.csv", state_rows)
        write_csv(output_dir / "csm_dependency_trace_audit.csv", dependency_rows)
        write_csv(output_dir / "csm_lineage_resolution_audit.csv", lineage_rows)
        write_failure_analysis(output_dir / "csm_v1_failure_analysis.md")
        print(json.dumps(report, indent=2, default=str))
        return 0 if report["status"] == "passed" else 1
    finally:
        db.close()


def audit_source_scope(db, *, source_id, case_id, repetition: int, expected_questions: int) -> list[dict]:
    rows = []
    expected_baseline_turns = (len(CSM_V2_COMPARISON_SYSTEM_TYPES) - 1) * expected_questions
    baseline_turns = 0
    csm_turns = 0

    for system in CSM_V2_COMPARISON_SYSTEM_TYPES:
        run = db.scalar(
            select(ExperimentSystemRun).where(
                ExperimentSystemRun.experiment_id == source_id,
                ExperimentSystemRun.case_id == case_id,
                ExperimentSystemRun.system_type == system,
                ExperimentSystemRun.repetition_number == repetition,
            )
        )
        status = "failed"
        detail = "missing_run"
        count = 0
        if run is not None:
            count = int(
                db.scalar(
                    select(ExperimentTurn.id)
                    .where(ExperimentTurn.system_run_id == run.id, ExperimentTurn.status == "completed")
                    .limit(1)
                )
                is not None
            )
            turn_count = len(db.scalars(select(ExperimentTurn).where(ExperimentTurn.system_run_id == run.id)).all())
            output_count = len(
                db.scalars(
                    select(ExperimentOutput)
                    .join(ExperimentTurn, ExperimentOutput.turn_id == ExperimentTurn.id)
                    .where(ExperimentTurn.system_run_id == run.id)
                ).all()
            )
            status = "passed" if run.status == "completed" and turn_count == expected_questions and output_count == expected_questions else "failed"
            detail = f"run_status={run.status}; turns={turn_count}; outputs={output_count}"
            if system == "csm":
                csm_turns += turn_count
            else:
                baseline_turns += turn_count
        rows.append(row("source_scope", f"source_{system}_completed", status, "critical", detail))

    rows.append(
        row(
            "source_scope",
            "frozen_non_csm_baseline_turn_count",
            "passed" if baseline_turns == expected_baseline_turns else "failed",
            "critical",
            f"expected={expected_baseline_turns}; observed={baseline_turns}",
        )
    )
    rows.append(
        row(
            "source_scope",
            "source_csm_turn_count",
            "passed" if csm_turns == expected_questions else "failed",
            "warning",
            f"expected={expected_questions}; observed={csm_turns}; source_csm_is_not_reused_for_v2_generation",
        )
    )
    return rows


def audit_derived_scope(db, *, derived_id, case_id, repetition: int, expected_questions: int) -> list[dict]:
    rows = []
    baseline_turns = 0
    pending_csm = False

    for system in CSM_V2_COMPARISON_SYSTEM_TYPES:
        run = db.scalar(
            select(ExperimentSystemRun).where(
                ExperimentSystemRun.experiment_id == derived_id,
                ExperimentSystemRun.case_id == case_id,
                ExperimentSystemRun.system_type == system,
                ExperimentSystemRun.repetition_number == repetition,
            )
        )
        if run is None:
            rows.append(row("derived_scope", f"derived_{system}_run_exists", "failed", "critical", "missing_run"))
            continue
        turn_count = len(db.scalars(select(ExperimentTurn).where(ExperimentTurn.system_run_id == run.id)).all())
        if system == "csm":
            pending_csm = run.status == "pending" and turn_count == 0
            rows.append(
                row(
                    "derived_scope",
                    "derived_csm_pending_only",
                    "passed" if pending_csm else "failed",
                    "critical",
                    f"status={run.status}; turns={turn_count}",
                )
            )
        else:
            baseline_turns += turn_count
            frozen = bool((run.configuration_snapshot or {}).get("frozen_baseline"))
            rows.append(
                row(
                    "derived_scope",
                    f"derived_{system}_frozen",
                    "passed" if run.status == "completed" and frozen and turn_count == expected_questions else "failed",
                    "critical",
                    f"status={run.status}; frozen={frozen}; turns={turn_count}",
                )
            )

    rows.append(
        row(
            "derived_scope",
            "derived_baseline_turns_reused",
            "passed" if baseline_turns == (len(CSM_V2_COMPARISON_SYSTEM_TYPES) - 1) * expected_questions else "failed",
            "critical",
            f"baseline_turns={baseline_turns}",
        )
    )
    return rows


def non_patient_one_invariant_rows() -> list[dict]:
    rows = []
    correction_route = route_query("After the amended electrolyte report, which sodium value should be treated as current?")
    rows.append(
        row(
            "router",
            "generic_correction_route",
            "passed" if correction_route.mode == "correction_state" else "failed",
            "critical",
            f"mode={correction_route.mode}; reason={correction_route.reason}",
        )
    )

    original = synthetic_source("Measurement: Sodium. Value: 128. Unit: mmol/L.", {"observation_name": "Sodium", "value_numeric": 128, "unit": "mmol/L"}, "hash-a")
    revised = synthetic_source("Measurement: Sodium. Value: 136. Unit: mmol/L.", {"observation_name": "Sodium", "value_numeric": 136, "unit": "mmol/L"}, "hash-b")
    original_evidence = synthetic_evidence(original)
    revised_evidence = synthetic_evidence(revised)
    previous = build_state_value_payload(
        source=original,
        evidence=original_evidence,
        operation="upsert",
        version=1,
        previous_value=None,
        supersedes=[],
        dependency_ids=[],
    )
    rows.append(
        row(
            "state_schema",
            "generic_state_schema_version",
            "passed" if previous.get("schema_version") == CSM_V2_STATE_SCHEMA_VERSION else "failed",
            "critical",
            f"schema_version={previous.get('schema_version')}",
        )
    )
    rows.append(
        row(
            "supersession",
            "generic_newer_same_key_supersedes",
            "passed" if should_supersede(previous, revised, revised_evidence) else "failed",
            "critical",
            "synthetic sodium correction uses no Patient 1 identifiers",
        )
    )
    return rows


def state_replay_rows(db, *, patient: str) -> list[dict]:
    rows = []
    instances = csm_instances(db, patient=patient)
    for instance in instances:
        states = list(
            db.scalars(
                select(CsmStateVariable).where(CsmStateVariable.system_instance_id == instance.id)
            ).all()
        )
        for state in states:
            value = state.current_value or {}
            rows.append(
                {
                    "patient": patient,
                    "system_instance_id": str(instance.id),
                    "state_id": str(state.id),
                    "state_type": state.state_type,
                    "state_key": state.state_key,
                    "version": state.current_version,
                    "schema_version": value.get("schema_version"),
                    "implementation_version": value.get("implementation_version"),
                    "status": state.status,
                    "has_lineage": bool(value.get("lineage")),
                    "has_evidence_ids": bool(value.get("evidence_ids")),
                    "has_dependency_ids": "dependency_ids" in value,
                    "audit_status": "passed" if value.get("schema_version") in {None, CSM_V2_STATE_SCHEMA_VERSION} else "failed",
                }
            )
    if not rows:
        rows.append({"patient": patient, "audit_status": "no_csm_states_materialized_yet"})
    return rows


def dependency_trace_rows(db, *, patient: str) -> list[dict]:
    rows = []
    for instance in csm_instances(db, patient=patient):
        dependencies = list(
            db.scalars(
                select(CsmStateDependency).where(CsmStateDependency.system_instance_id == instance.id)
            ).all()
        )
        for dep in dependencies:
            rows.append(
                {
                    "patient": patient,
                    "system_instance_id": str(instance.id),
                    "dependency_id": str(dep.id),
                    "source_state_id": str(dep.source_state_id),
                    "target_state_id": str(dep.target_state_id),
                    "relation_type": dep.relation_type,
                    "weight": dep.weight,
                    "status": dep.status,
                }
            )
    if not rows:
        rows.append({"patient": patient, "audit_status": "no_dependencies_materialized_yet"})
    return rows


def lineage_rows_for_csm(db, *, patient: str) -> list[dict]:
    rows = []
    for instance in csm_instances(db, patient=patient):
        links = list(
            db.execute(
                select(CsmStateVariable, CsmStateEvidenceLink, CsmEvidence)
                .join(CsmStateEvidenceLink, CsmStateEvidenceLink.state_variable_id == CsmStateVariable.id)
                .join(CsmEvidence, CsmStateEvidenceLink.evidence_id == CsmEvidence.id)
                .where(CsmStateVariable.system_instance_id == instance.id)
            ).all()
        )
        for state, link, evidence in links:
            rows.append(
                {
                    "patient": patient,
                    "state_id": str(state.id),
                    "state_key": state.state_key,
                    "evidence_id": str(evidence.id),
                    "canonical_source_id": str(evidence.canonical_source_id),
                    "document_id": str(evidence.document_id) if evidence.document_id else "",
                    "page_number": evidence.page_number,
                    "section_id": str(evidence.section_id) if evidence.section_id else "",
                    "contribution_type": link.contribution_type,
                    "audit_status": "passed" if evidence.canonical_source_id else "failed",
                }
            )
    if not rows:
        rows.append({"patient": patient, "audit_status": "no_lineage_links_materialized_yet"})
    return rows


def csm_instances(db, *, patient: str) -> list[MemorySystemInstance]:
    patient_codes = {patient, f"EVAL-{patient}"}
    patient_ids = [
        row.id
        for row in db.scalars(select(Patient).where(Patient.patient_code.in_(patient_codes))).all()
    ]
    if not patient_ids:
        return []

    return list(
        db.scalars(
            select(MemorySystemInstance)
            .where(
                MemorySystemInstance.system_type == "csm",
                MemorySystemInstance.patient_id.in_(patient_ids),
            )
        ).all()
    )


def synthetic_source(text: str, payload: dict, content_hash: str):
    now = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    return SimpleNamespace(
        id=uuid4(),
        source_type="patient_information",
        source_subtype="measurement",
        source_record_id=str(uuid4()),
        source_version="synthetic",
        content_text=text,
        structured_payload=payload,
        content_hash=content_hash,
        event_time=now,
        valid_time=now,
        recorded_time=now,
        document_id=None,
        page_number=None,
        section_id=None,
    )


def synthetic_evidence(source):
    return CsmEvidence(
        id=uuid4(),
        system_instance_id=uuid4(),
        canonical_source_id=source.id,
        evidence_type="structured_measurement",
        observation_type="measurement",
        content=source.content_text,
        structured_value=source.structured_payload,
        normalized_value="synthetic-measurement",
        unit=source.structured_payload.get("unit"),
        source_type=source.source_type,
        document_id=None,
        page_number=None,
        section_id=None,
        conversation_id=None,
        message_id=None,
        valid_time=source.valid_time,
        recorded_time=source.recorded_time,
        confidence=0.9,
        verification_status="verified",
        extraction_method="synthetic_preflight",
        extractor_version="2",
        is_active=True,
    )


def row(category: str, check: str, status: str, severity: str, detail: str) -> dict:
    return {
        "category": category,
        "check": check,
        "status": status,
        "severity": severity,
        "detail": detail,
    }


def write_failure_analysis(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "# CSM v1 Failure Analysis",
                "",
                "The prior CSM adapter activated state variables without canonical source IDs, so final-answer citations could not reliably resolve through the standard lineage evaluator.",
                "Document evidence was ingested as candidate state but v1 retrieval considered only active states, which suppressed many raw source facts needed for exact-source, correction, and rare-detail questions.",
                "The v1 router was a lexical state match only; it did not separate temporal, correction, dependency, evidence-first, exact-source, or high-risk review needs.",
                "State versions stored basic source hashes but did not carry a compact generic schema with explicit lineage, supersession, dependency, confidence-component, and uncertainty-component fields.",
                "Conversation and document claims lacked a deterministic fallback path into answer-generation context, making abstention and evidence support inconsistent across query types.",
                "",
            ]
        ),
        encoding="utf-8",
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
