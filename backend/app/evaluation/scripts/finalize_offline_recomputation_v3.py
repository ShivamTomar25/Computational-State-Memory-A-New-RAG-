from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import re
import shutil
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SYSTEMS = ["long_context", "rolling_summary", "dense_rag", "hybrid_rag", "graph_rag", "hippo_rag", "csm"]
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
EXTRA_METRICS = ["answer_precision", "answer_recall", "activation_precision", "activation_recall"]
METRICS = BASE_METRICS + EXTRA_METRICS
AFFECTED_METRICS = {
    "answer_accuracy",
    "answer_precision",
    "answer_recall",
    "retrieval_precision",
    "retrieval_recall",
    "lineage_citation_f1",
    "state_accuracy",
    "decision_f1",
    "temporal_consistency",
    "correction_recovery",
    "faithfulness",
    "p95_latency",
    "activation_precision",
    "activation_recall",
}
LOWER_IS_BETTER = {
    "hallucination_rate",
    "unsupported_claim_rate",
    "fabricated_citation_rate",
    "expected_calibration_error",
    "tokens_per_query",
    "p95_latency",
    "total_cost",
    "state_recovery_time",
}
NON_FACTUAL = {"not_factual", "insufficient_evidence_statement"}
SUPPORTED = {"supported", "partially_supported"}
EXPLICIT_DECISION_LABELS = {
    "urgent_escalation",
    "clinician_review",
    "no_follow_up",
    "pending_review",
    "insufficient_evidence",
    "reject_unverified_claim",
}
CORRECTION_QUESTION_REASONS = {
    6: "superseded_original_values_and_corrected_values_from_laboratory_addendum",
    7: "post_correction_pre_followup_renal_state_depends_on_corrected_values",
    8: "follow_up_recovery_after_corrected_values",
    11: "exact_corrected_creatinine_statement_from_laboratory_addendum",
    12: "improvement_evidence_depends_on_corrected_values_and_followup_recovery",
    16: "corrected_creatinine_citation_requires_laboratory_addendum_source",
    17: "renal_state_version_order_includes_correction_and_recovery",
    18: "corrected_value_must_be_excluded_before_addendum_cutoff",
    20: "renal_course_summary_depends_on_baseline_correction_and_recovery",
}
TEMPORAL_ASSERTIONS = {
    3: [
        {
            "assertion_id": "P1-Q03-T1",
            "event_a": "initial_5_march_renal_report",
            "relation": "available_by_cutoff_and_provisional",
            "event_b": "corrected_addendum_and_followup",
            "expected_latest_valid_source": "DOC-P1-002",
            "required_truth_claims": ["Initial report suggested worsening", "Conclusion was provisional"],
            "forbidden_terms": ["1.5", "53", "1.2", "70"],
        }
    ],
    4: [
        {
            "assertion_id": "P1-Q04-T1",
            "event_a": "dehydration_episode_valid_time_2026-03-04",
            "relation": "valid_time_precedes_ingestion_time",
            "event_b": "dehydration_note_recorded_2026-03-10",
            "expected_latest_valid_source": "DOC-P1-004",
            "required_truth_claims": ["Dehydration occurred 4 March", "It was recorded 10 March"],
            "forbidden_terms": [],
        }
    ],
    5: [
        {
            "assertion_id": "P1-Q05-T1",
            "event_a": "dehydration_note",
            "relation": "qualifies_but_does_not_erase_abnormal_result",
            "event_b": "initial_abnormal_renal_result",
            "expected_latest_valid_source": "DOC-P1-004",
            "required_truth_claims": ["Dehydration may have influenced result", "Evidence should not be erased"],
            "forbidden_terms": [],
        }
    ],
    6: [
        {
            "assertion_id": "P1-Q06-T1",
            "event_a": "original_5_march_report_values",
            "relation": "superseded_by",
            "event_b": "12_march_corrected_addendum_values",
            "expected_latest_valid_source": "DOC-P1-005",
            "required_truth_claims": ["1.8 superseded by 1.5", "42 superseded by 53"],
            "forbidden_terms": [],
        }
    ],
    7: [
        {
            "assertion_id": "P1-Q07-T1",
            "event_a": "corrected_addendum_state",
            "relation": "latest_valid_before_followup",
            "event_b": "20_march_followup",
            "expected_latest_valid_source": "DOC-P1-005",
            "required_truth_claims": ["Corrected values remain abnormal", "Dehydration qualifies interpretation"],
            "forbidden_terms": ["1.2", "70"],
        }
    ],
    8: [
        {
            "assertion_id": "P1-Q08-T1",
            "event_a": "20_march_followup",
            "relation": "after_correction_shows_recovery",
            "event_b": "corrected_5_march_state",
            "expected_latest_valid_source": "DOC-P1-006",
            "required_truth_claims": ["Creatinine improved to 1.2", "eGFR improved to 70", "Trend improved toward baseline"],
            "forbidden_terms": [],
        }
    ],
    13: [
        {
            "assertion_id": "P1-Q13-T1",
            "event_a": "5_march_abnormal_values",
            "relation": "valid_time_precedes_ingestion_time",
            "event_b": "8_march_application_receipt",
            "expected_latest_valid_source": "DOC-P1-002",
            "required_truth_claims": ["Valid date 5 March"],
            "forbidden_terms": ["same day"],
        }
    ],
    17: [
        {
            "assertion_id": "P1-Q17-T1",
            "event_a": "renal_state_versions",
            "relation": "ordered_baseline_worsening_qualified_corrected_recovered",
            "event_b": "current_recovered_state",
            "expected_latest_valid_source": "DOC-P1-006",
            "required_truth_claims": ["State history preserves prior versions"],
            "forbidden_terms": [],
        }
    ],
    18: [
        {
            "assertion_id": "P1-Q18-T1",
            "event_a": "pre_12_march_cutoff",
            "relation": "corrected_value_not_yet_available",
            "event_b": "12_march_corrected_addendum",
            "expected_latest_valid_source": "DOC-P1-002",
            "required_truth_claims": ["Corrected value unavailable before cutoff"],
            "forbidden_terms": ["1.5 mg/dl", "53 ml/min"],
        }
    ],
    20: [
        {
            "assertion_id": "P1-Q20-T1",
            "event_a": "full_renal_course",
            "relation": "ordered_baseline_initial_decline_correction_qualification_followup",
            "event_b": "medium_high_confidence_summary",
            "expected_latest_valid_source": "DOC-P1-006",
            "required_truth_claims": [
                "Baseline preserved",
                "Initial decline",
                "Dehydration qualification",
                "Correction",
                "Follow-up improvement",
            ],
            "forbidden_terms": [],
        }
    ],
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Final v3 offline correction pass over Sustha Patient 1 v2 outputs.")
    parser.add_argument(
        "--input-dir",
        default="../evaluation/results/corrected_offline_recomputation_v2/SYN-CSM-001/repetition_1/20260722T093602Z",
    )
    parser.add_argument("--output-root", default="../evaluation/results/corrected_offline_recomputation_v3")
    parser.add_argument("--patient", default="SYN-CSM-001")
    parser.add_argument("--repetition", type=int, default=1)
    args = parser.parse_args()

    input_dir = Path(args.input_dir).resolve()
    if not input_dir.exists():
        raise SystemExit(f"Input directory not found: {input_dir}")
    output_dir = (
        Path(args.output_root)
        / args.patient
        / f"repetition_{args.repetition}"
        / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ).resolve()
    output_dir.mkdir(parents=True, exist_ok=False)

    data = load_v2(input_dir, args.patient)
    validation = validate_input(data, args.patient)
    if validation["status"] != "passed":
        write_json(output_dir / "scope_validation.json", validation)
        raise SystemExit("Input validation failed; v3 export rejected.")

    resolver = CanonicalResolver(data)
    identifier_rows, generated_canonical_by_turn = build_identifier_resolution(data, resolver)
    answer_audit, answer_observations = build_answer_f1(data)
    retrieval_audit, retrieval_observations = build_retrieval_metrics(data, resolver)
    lineage_observations = build_lineage_metrics(data, resolver, generated_canonical_by_turn)
    state_mapping_audit, state_observations = build_state_metrics(data)
    decision_audit, decision_observations = build_decision_metrics(data)
    temporal_audit, temporal_observations = build_temporal_metrics(data)
    correction_audit, correction_observations = build_correction_metrics(data)
    faithfulness_audit, faithfulness_observations = build_faithfulness_metrics(data)
    latency_audit, latency_observations = build_latency_metrics(data)
    activation_observations = build_activation_metrics(data, resolver)

    corrected = replace_observations(
        data["metric_observations"],
        answer_observations
        + retrieval_observations
        + lineage_observations
        + state_observations
        + decision_observations
        + temporal_observations
        + correction_observations
        + faithfulness_observations
        + latency_observations
        + activation_observations,
    )

    matrix = aggregate(corrected)
    rankings = rank(matrix)
    stats = paired_stats(corrected)
    old_vs_new = compare_old_new(data["system_metric_matrix"], matrix)
    verification = verify_export(data, corrected, matrix, stats)
    if verification["status"] != "passed":
        write_json(output_dir / "verification_rejection.json", verification)
        raise SystemExit("V3 verification failed; export rejected.")

    copy_preserved_files(input_dir, output_dir)
    write_json(output_dir / "scope_validation.json", validation)
    write_csv(output_dir / "metric_observations.csv", corrected)
    write_csv(output_dir / "system_metric_matrix.csv", matrix)
    write_json(output_dir / "system_metric_matrix.json", matrix)
    write_csv(output_dir / "metric_rankings.csv", rankings)
    write_json(output_dir / "metric_rankings.json", rankings)
    write_csv(output_dir / "statistical_results.csv", stats)
    write_json(output_dir / "statistical_results.json", stats)
    write_csv(output_dir / "answer_f1_audit.csv", answer_audit)
    write_csv(output_dir / "canonical_evidence_identifier_resolution_audit.csv", identifier_rows)
    write_csv(output_dir / "retrieval_identifier_resolution_audit.csv", retrieval_audit)
    write_csv(output_dir / "state_key_mapping_audit.csv", state_mapping_audit)
    write_csv(output_dir / "decision_label_audit.csv", decision_audit)
    write_csv(output_dir / "temporal_assertion_audit.csv", temporal_audit)
    write_csv(output_dir / "correction_recovery_audit.csv", correction_audit)
    write_csv(output_dir / "faithfulness_entailment_audit.csv", faithfulness_audit)
    write_csv(output_dir / "latency_definition_audit.csv", latency_audit)
    write_csv(output_dir / "old_vs_new_metric_comparison.csv", old_vs_new)
    write_csv(output_dir / "paper_complete_21_metric_matrix.csv", paper_matrix(matrix, BASE_METRICS))
    write_csv(output_dir / "paper_complete_v3_metric_matrix.csv", paper_matrix(matrix, METRICS))
    write_text(output_dir / "paper_results_summary.md", paper_summary(validation, corrected, matrix, old_vs_new))
    write_text(output_dir / "retrieval_manual_sanity_check.md", retrieval_sanity_text(retrieval_audit, matrix))
    write_json(
        output_dir / "metric_recomputation_manifest.json",
        {
            "title": "Sustha Single-Patient Synthetic Case-Study Results",
            "version": "corrected_offline_recomputation_v3",
            "input_dir": str(input_dir),
            "output_dir": str(output_dir),
            "patient": args.patient,
            "questions": 20,
            "systems": 7,
            "repetitions": 1,
            "completed_turns": 140,
            "zero_provider_calls": True,
            "stored_answers_modified": False,
            "metric_observation_count": len(corrected),
            "affected_metrics_corrected": [
                *sorted(AFFECTED_METRICS),
            ],
        },
    )
    print(json.dumps({"status": "completed", "output_dir": str(output_dir), "metric_observations": len(corrected)}, indent=2))
    return 0


def load_v2(input_dir: Path, patient: str) -> dict[str, Any]:
    sustha_root = Path(__file__).resolve().parents[4]
    pack_root = sustha_root / "sustha_three_patient_evaluation_pack"
    patient_root = pack_root / "patients" / patient
    pilot_dir = sustha_root / "evaluation" / "results" / "sustha_three_patient_pilot" / "20260722T064854Z"
    return {
        "metric_observations": read_csv(input_dir / "metric_observations.csv"),
        "claim_matching": read_csv(input_dir / "claim_matching_audit.csv"),
        "claim_support": read_csv(input_dir / "claim_support_audit.csv"),
        "citations": read_csv(input_dir / "citation_resolution_audit.csv"),
        "states": read_csv(input_dir / "state_comparison_audit.csv"),
        "csm_activation": read_csv(input_dir / "csm_activation_audit.csv"),
        "system_metric_matrix": read_csv(input_dir / "system_metric_matrix.csv"),
        "scope_validation": read_json(input_dir / "scope_validation.json"),
        "answer_preservation": read_json(input_dir / "answer_preservation_audit.json"),
        "csm_lineage": read_json(input_dir / "csm_lineage_trace.json"),
        "csm_state_trace": read_json(input_dir / "csm_state_trace.json"),
        "ground_truth": read_json(patient_root / "ground_truth.json"),
        "expected_state_snapshots": read_json(patient_root / "expected_state_snapshots.json"),
        "document_metadata": read_json(patient_root / "document_metadata.json"),
        "structured_information": read_json(patient_root / "structured_information.json"),
        "retrieval_traces": read_json(pilot_dir / "retrieval_traces.json"),
        "latency_results": read_csv(pilot_dir / "latency_results.csv"),
        "input_dir": input_dir,
        "patient": patient,
    }


def validate_input(data: dict[str, Any], patient: str) -> dict[str, Any]:
    turns = {row["turn_id"] for row in data["metric_observations"]}
    systems = {row["system"] for row in data["metric_observations"]}
    questions_by_system = defaultdict(set)
    for row in data["metric_observations"]:
        questions_by_system[row["system"]].add(row["question_number"])
    errors = []
    if len(turns) != 140:
        errors.append(f"expected_140_turns_found_{len(turns)}")
    if systems != set(SYSTEMS):
        errors.append(f"expected_7_systems_found_{sorted(systems)}")
    for system in SYSTEMS:
        if len(questions_by_system[system]) != 20:
            errors.append(f"{system}_expected_20_questions_found_{len(questions_by_system[system])}")
    if len(data["metric_observations"]) < 2940:
        errors.append(f"expected_at_least_2940_observations_found_{len(data['metric_observations'])}")
    if not data["answer_preservation"].get("zero_groq_calls", True):
        errors.append("answer_preservation_audit_does_not_confirm_zero_provider_calls")
    return {
        "status": "passed" if not errors else "failed",
        "errors": errors,
        "patient": patient,
        "questions": 20,
        "systems": 7,
        "repetitions": 1,
        "completed_turns": 140,
        "included_turns": len(turns),
        "counts_per_system": {system: len(questions_by_system[system]) for system in SYSTEMS},
        "summary_label": "Sustha Single-Patient Synthetic Case-Study Results",
    }


class CanonicalResolver:
    def __init__(self, data: dict[str, Any]):
        self.data = data
        self.source_to_canonicals: dict[str, set[str]] = defaultdict(set)
        self.evidence_to_sources: dict[str, set[str]] = defaultdict(set)
        self.evidence_to_canonicals: dict[str, set[str]] = defaultdict(set)
        self.canonical_to_family: dict[str, str] = {}
        self.state_to_canonicals: dict[str, set[str]] = defaultdict(set)
        self.state_evidence_to_canonicals: dict[str, set[str]] = defaultdict(set)
        self.local_citations: dict[tuple[str, str], set[str]] = defaultdict(set)
        self.document_uuid_to_source: dict[str, str] = {}
        self.question_by_number = {
            int(q["question_id"].split("-Q")[-1]): q
            for q in data["ground_truth"]["questions"]
            if q.get("question_id", "").startswith("P1-Q")
        }
        self.question_number_by_text = {
            normalize_text(q.get("question_text")): int(q["question_id"].split("-Q")[-1])
            for q in data["ground_truth"]["questions"]
            if q.get("question_id", "").startswith("P1-Q")
        }
        self._build_document_maps()
        self._build_trace_maps()
        self._build_csm_maps()
        self._build_citation_maps()

    def _build_document_maps(self) -> None:
        for doc in self.data["document_metadata"]:
            doc_id = doc.get("document_id")
            if not doc_id:
                continue
            for evidence_id in doc.get("evidence_ids", []):
                self.evidence_to_sources[evidence_id].add(doc_id)

    def _build_trace_maps(self) -> None:
        for row in self.data["retrieval_traces"]:
            canonical = row.get("canonical_source_id")
            if not canonical:
                continue
            preview = row.get("content_preview", "")
            source_ids = extract_benchmark_ids(preview)
            doc_uuid = row.get("document_id")
            for source_id in source_ids:
                self.source_to_canonicals[source_id].add(canonical)
                self.canonical_to_family.setdefault(canonical, source_id)
                if doc_uuid and source_id.startswith("DOC-P1-"):
                    self.document_uuid_to_source[doc_uuid] = source_id
            for evidence_id in extract_evidence_ids(preview):
                self.evidence_to_canonicals[evidence_id].add(canonical)
                if source_ids:
                    for source_id in source_ids:
                        if source_id.startswith("DOC-P1-"):
                            self.evidence_to_sources[evidence_id].add(source_id)

    def _build_csm_maps(self) -> None:
        state_rows_by_id = {row.get("state_id"): row for row in self.data["csm_state_trace"]}
        for lineage in self.data["csm_lineage"]:
            canonical = lineage.get("canonical_source_id")
            state_id = lineage.get("state_id")
            evidence_id = lineage.get("evidence_id")
            if state_id and canonical:
                self.state_to_canonicals[state_id].add(canonical)
            if evidence_id and canonical:
                self.state_evidence_to_canonicals[evidence_id].add(canonical)
            state = state_rows_by_id.get(state_id, {})
            text = json.dumps(state.get("current_value", {}), sort_keys=True, default=str)
            source_ids = extract_benchmark_ids(text)
            for source_id in source_ids:
                self.source_to_canonicals[source_id].add(canonical)
                self.canonical_to_family.setdefault(canonical, source_id)
            for source_id in source_ids:
                if source_id.startswith("EV-P1-"):
                    self.evidence_to_canonicals[source_id].add(canonical)
            if canonical and canonical not in self.canonical_to_family:
                self.canonical_to_family[canonical] = state.get("state_key") or canonical

    def _build_citation_maps(self) -> None:
        for row in self.data["citations"]:
            citation_id = row.get("citation_id")
            resolved = row.get("resolved_id")
            turn_id = row.get("turn_id")
            if citation_id and resolved and turn_id:
                self.local_citations[(turn_id, citation_id)].add(resolved)
            if resolved and resolved not in self.canonical_to_family:
                self.canonical_to_family[resolved] = resolved

    def question(self, question_number: Any) -> dict[str, Any]:
        return self.question_by_number.get(int(question_number), {})

    def family(self, canonical_source_id: str) -> str:
        return self.canonical_to_family.get(canonical_source_id, canonical_source_id)

    def resolve(self, identifier: Any, turn_id: str | None = None) -> list[dict[str, Any]]:
        original = str(identifier or "").strip()
        if not original:
            return [self._resolution(original, "unknown_identifier", "", "empty_identifier", "unresolved")]
        identifier_type = identifier_type_for(original)
        canonicals: set[str] = set()
        method = "unresolved"
        if turn_id and (turn_id, original) in self.local_citations:
            canonicals |= self.local_citations[(turn_id, original)]
            method = "local_citation_alias_to_canonical_source"
        elif original in self.source_to_canonicals:
            canonicals |= self.source_to_canonicals[original]
            method = "benchmark_source_id_to_canonical_source"
        elif original in self.evidence_to_canonicals:
            canonicals |= self.evidence_to_canonicals[original]
            method = "benchmark_evidence_id_to_canonical_source"
        elif original in self.evidence_to_sources:
            for source_id in self.evidence_to_sources[original]:
                canonicals |= self.source_to_canonicals.get(source_id, set())
            method = "benchmark_evidence_id_to_document_source_to_canonical"
        elif original in self.state_to_canonicals:
            canonicals |= self.state_to_canonicals[original]
            method = "csm_state_id_to_state_evidence_link_to_canonical_source"
        elif original in self.state_evidence_to_canonicals:
            canonicals |= self.state_evidence_to_canonicals[original]
            method = "csm_evidence_id_to_canonical_source"
        elif original in self.document_uuid_to_source:
            source_id = self.document_uuid_to_source[original]
            canonicals |= self.source_to_canonicals.get(source_id, set())
            method = "source_record_uuid_to_document_source_to_canonical"
        elif is_uuid(original):
            canonicals.add(original)
            method = "already_canonical_source_uuid_or_source_record_uuid"
        if not canonicals:
            return [self._resolution(original, identifier_type, "", method, "unresolved")]
        return [
            self._resolution(original, identifier_type, canonical, method, "resolved")
            | {"canonical_family_id": self.family(canonical)}
            for canonical in sorted(canonicals)
        ]

    def _resolution(self, original: str, identifier_type: str, canonical: str, method: str, status: str) -> dict[str, Any]:
        return {
            "original_identifier": original,
            "identifier_type": identifier_type,
            "canonical_source_id": canonical,
            "resolution_method": method,
            "resolution_status": status,
            "canonical_family_id": self.family(canonical) if canonical else "",
        }

    def expected_retrieval_families(self, question_number: Any) -> set[str]:
        question = self.question(question_number)
        retrieval_gt = question.get("retrieval_ground_truth", {})
        families = set()
        for identifier in retrieval_gt.get("mandatory_relevant_source_ids", []):
            families.add(identifier)
            for resolved in self.resolve(identifier):
                if resolved["resolution_status"] == "resolved":
                    families.add(resolved["canonical_family_id"])
        return families

    def expected_lineage_families(self, question_number: Any) -> set[str]:
        question = self.question(question_number)
        families = set()
        for identifier in question.get("expected_evidence_ids", []) + question.get("expected_relevant_source_ids", []):
            if identifier:
                families.add(identifier)
            for resolved in self.resolve(identifier):
                if resolved["resolution_status"] == "resolved":
                    families.add(resolved["canonical_family_id"])
        return families

    def retrieved_canonicals_for_turn(self, base: dict[str, Any]) -> set[str]:
        turn_id = base.get("turn_id")
        system = base.get("system")
        if system == "csm":
            question = self.question(base.get("question_number"))
            query = normalize_text(question.get("question_text"))
            canonicals = set()
            for row in self.data["csm_activation"]:
                if normalize_text(row.get("query_text")) != query or not parse_bool(row.get("selected")):
                    continue
                for resolved in self.resolve(row.get("state_variable_id")):
                    if resolved["resolution_status"] == "resolved":
                        canonicals.add(resolved["canonical_source_id"])
            return canonicals
        return {
            row.get("canonical_source_id")
            for row in self.data["retrieval_traces"]
            if row.get("turn_id") == turn_id and row.get("canonical_source_id")
        }


def build_identifier_resolution(data: dict[str, Any], resolver: CanonicalResolver) -> tuple[list[dict], dict[str, set[str]]]:
    rows = []
    canonical_by_turn = defaultdict(set)
    for row in data["citations"]:
        for resolved in resolver.resolve(row.get("citation_id"), row.get("turn_id")):
            rows.append(
                base_from(row)
                | resolved
                | {
                    "item_class": "generated_citation",
                    "source_table": "citation_resolution_audit.csv",
                    "citation_classification": row.get("citation_classification"),
                }
            )
            if resolved["resolution_status"] == "resolved":
                canonical_by_turn[row["turn_id"]].add(resolved["canonical_source_id"])
        if row.get("resolved_id"):
            for resolved in resolver.resolve(row.get("resolved_id"), row.get("turn_id")):
                rows.append(
                    base_from(row)
                    | resolved
                    | {
                        "item_class": "generated_citation_resolved_id",
                        "source_table": "citation_resolution_audit.csv",
                        "citation_classification": row.get("citation_classification"),
                    }
                )
    for lineage in data["csm_lineage"]:
        for key in ("state_id", "evidence_id", "canonical_source_id"):
            for resolved in resolver.resolve(lineage.get(key)):
                rows.append(
                    {
                        "patient": data["patient"],
                        "question_id": "",
                        "question_number": "",
                        "system": "csm",
                        "turn_id": "",
                    }
                    | resolved
                    | {"item_class": "csm_lineage", "source_table": "csm_lineage_trace.json"}
                )
    for trace in data["retrieval_traces"]:
        original = trace.get("canonical_source_id") or trace.get("content_preview")
        for resolved in resolver.resolve(original):
            rows.append(
                {
                    "patient": data["patient"],
                    "question_id": "",
                    "question_number": "",
                    "system": trace.get("system"),
                    "turn_id": trace.get("turn_id"),
                }
                | resolved
                | {
                    "item_class": "retrieved_source",
                    "source_table": "retrieval_traces.json",
                    "rank": trace.get("rank"),
                    "source_type": trace.get("source_type"),
                }
            )
    for activation in data["csm_activation"]:
        qn = resolver.question_number_by_text.get(normalize_text(activation.get("query_text")), "")
        for resolved in resolver.resolve(activation.get("state_variable_id")):
            rows.append(
                {
                    "patient": data["patient"],
                    "question_id": question_code(qn) if qn else "",
                    "question_number": qn,
                    "system": "csm",
                    "turn_id": "",
                }
                | resolved
                | {
                    "item_class": "activated_state",
                    "source_table": "csm_activation_audit.csv",
                    "selected": activation.get("selected"),
                    "rank": activation.get("rank"),
                }
            )
    for qn, question in resolver.question_by_number.items():
        expected_ids = (
            question.get("expected_evidence_ids", [])
            + question.get("expected_relevant_source_ids", [])
            + question.get("retrieval_ground_truth", {}).get("mandatory_relevant_source_ids", [])
        )
        for original in sorted(set(expected_ids)):
            for resolved in resolver.resolve(original):
                rows.append(
                    {
                        "patient": data["patient"],
                        "question_id": question.get("question_id"),
                        "question_number": qn,
                        "system": "benchmark_ground_truth",
                        "turn_id": "",
                    }
                    | resolved
                    | {"item_class": "expected_evidence_or_source", "source_table": "ground_truth.json"}
                )
    return rows, canonical_by_turn


def build_answer_f1(data: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    matches_by_turn = group(data["claim_matching"], "turn_id")
    support_by_claim = {(row["turn_id"], row["claim_id"]): row for row in data["claim_support"]}
    base_by_turn = {row["turn_id"]: base_from(row) for row in data["metric_observations"]}
    gt_by_question = {
        int(q["question_id"].split("-Q")[-1]): q
        for q in data["ground_truth"]["questions"]
        if q.get("question_id", "").startswith("P1-Q")
    }
    audit = []
    observations = []
    for turn_id, base in base_by_turn.items():
        rows = matches_by_turn.get(turn_id, [])
        question = gt_by_question.get(int(base["question_number"]), {})
        required_claims = list(question.get("required_claims", []))
        acceptable_claims = list(question.get("acceptable_claims", []))
        required_truth_ids = {truth_claim_id(base["question_number"], claim): claim for claim in required_claims}
        acceptable_truth_ids = {truth_claim_id(base["question_number"], claim, "A"): claim for claim in acceptable_claims}
        claim_text_to_truth_id = {normalize_claim_text(text): claim_id for claim_id, text in (required_truth_ids | acceptable_truth_ids).items()}
        tp_ids = []
        fp_ids = []
        credited_truth = set()
        for row in rows:
            support = support_by_claim.get((turn_id, row["claim_id"]), {})
            status = support.get("support_classification")
            factual = status not in NON_FACTUAL
            if not factual:
                continue
            matched_truth = claim_text_to_truth_id.get(normalize_claim_text(row.get("matched_ground_truth_claim")))
            correct = parse_bool(row.get("correctness")) and status in SUPPORTED and matched_truth and matched_truth not in credited_truth
            if correct:
                tp_ids.append(row["claim_id"])
                credited_truth.add(matched_truth)
            else:
                fp_ids.append(row["claim_id"])
        fn_truth = sorted(set(required_truth_ids) - credited_truth)
        tp = len(tp_ids)
        fp = len(fp_ids)
        fn = len(fn_truth)
        precision = tp / (tp + fp) if tp + fp else (0.0 if fn else None)
        recall = tp / (tp + fn) if tp + fn else None
        f1 = harmonic(precision, recall)
        audit.append(
            base
            | {
                "true_positive_claim_ids": json.dumps(tp_ids),
                "false_positive_claim_ids": json.dumps(fp_ids),
                "false_negative_claim_ids": json.dumps(fn_truth),
                "required_truth_claim_ids": json.dumps(sorted(required_truth_ids)),
                "acceptable_truth_claim_ids": json.dumps(sorted(acceptable_truth_ids)),
                "required_truth_claim_text_by_id": json.dumps(required_truth_ids, sort_keys=True),
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "answer_precision": precision,
                "answer_recall": recall,
                "answer_accuracy_f1": f1,
                "calculation_reason": "macro_claim_level_f1_with_unique_expected_claim_credit",
            }
        )
        observations.extend(
            [
                observation(base, "answer_precision", precision, precision is not None, "no_factual_generated_claims", tp, tp + fp if tp + fp else 0 if fn else None, "answer_f1_audit.csv", "TP/(TP+FP)"),
                observation(base, "answer_recall", recall, recall is not None, "no_expected_claim_match_candidates", tp, tp + fn if tp + fn else None, "answer_f1_audit.csv", "TP/(TP+FN)"),
                observation(base, "answer_accuracy", f1, f1 is not None, "no_expected_claim_match_candidates_or_factual_generated_claims", tp, tp + fp + fn if tp + fp + fn else None, "answer_f1_audit.csv", "claim_level_F1"),
            ]
        )
    return audit, observations


def build_retrieval_metrics(data: dict[str, Any], resolver: CanonicalResolver) -> tuple[list[dict], list[dict]]:
    audit = []
    observations = []
    turns = sorted({row["turn_id"] for row in data["metric_observations"]})
    base_by_turn = {row["turn_id"]: base_from(row) for row in data["metric_observations"]}
    for turn_id in turns:
        base = base_by_turn[turn_id]
        retrieved = resolver.retrieved_canonicals_for_turn(base)
        retrieved_families = {resolver.family(item) for item in retrieved}
        expected_families = resolver.expected_retrieval_families(base["question_number"])
        relevant_retrieved = {item for item in retrieved if resolver.family(item) in expected_families}
        satisfied_expected = expected_families & retrieved_families
        comparable = bool(retrieved and expected_families)
        precision = len(relevant_retrieved) / len(retrieved) if comparable else None
        recall = len(satisfied_expected) / len(expected_families) if comparable else None
        audit.append(
            base
            | {
                "unique_retrieved_canonical_ids": json.dumps(sorted(retrieved)),
                "retrieved_canonical_family_ids": json.dumps(sorted(retrieved_families)),
                "mandatory_expected_family_ids": json.dumps(sorted(expected_families)),
                "relevant_retrieved_canonical_ids": json.dumps(sorted(relevant_retrieved)),
                "satisfied_expected_family_ids": json.dumps(sorted(satisfied_expected)),
                "duplicate_family_equivalence_used": "canonical_family_id",
                "manual_sanity_status": "overlap_from_canonicalized_retrieval_trace" if comparable else "missing_retrieval_trace_or_expected_ground_truth",
            }
        )
        observations.append(observation(base, "retrieval_precision", precision, precision is not None, "missing_retrieval_trace_or_expected_ground_truth", len(relevant_retrieved), len(retrieved) if retrieved else None, "retrieval_identifier_resolution_audit.csv", "canonical_relevant_retrieved_over_unique_retrieved"))
        observations.append(observation(base, "retrieval_recall", recall, recall is not None, "missing_retrieval_trace_or_expected_ground_truth", len(satisfied_expected), len(expected_families) if expected_families else None, "retrieval_identifier_resolution_audit.csv", "canonical_expected_family_overlap_over_mandatory_expected"))
    return audit, observations


def build_lineage_metrics(data: dict[str, Any], resolver: CanonicalResolver, canonical_by_turn: dict[str, set[str]]) -> list[dict]:
    observations = []
    base_by_turn = {row["turn_id"]: base_from(row) for row in data["metric_observations"]}
    for turn_id, base in base_by_turn.items():
        generated = set(canonical_by_turn.get(turn_id, set()))
        generated_families = {resolver.family(item) for item in generated}
        expected_families = resolver.expected_lineage_families(base["question_number"])
        overlap = generated_families & expected_families
        precision = len(overlap) / len(generated_families) if generated_families else (0.0 if expected_families else None)
        recall = len(overlap) / len(expected_families) if expected_families else None
        value = harmonic(precision, recall)
        observations.append(observation(base, "lineage_citation_f1", value, value is not None, "no_generated_or_expected_canonical_citations", len(overlap), len(generated_families | expected_families), "canonical_evidence_identifier_resolution_audit.csv", "canonical_citation_family_precision_recall_f1"))
    return observations


def build_state_metrics(data: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    audit = []
    resolver = CanonicalResolver(data)
    snapshots = data["expected_state_snapshots"]
    snapshots_by_cutoff = {snapshot.get("cutoff"): snapshot for snapshot in snapshots}
    turns = [row for row in data["metric_observations"] if row["metric_name"] == "state_accuracy"]
    observations = []
    for row in turns:
        base = base_from(row)
        if base["system"] != "csm":
            observations.append(observation(base, "state_accuracy", None, False, "state_table_metric_only_applicable_to_csm", None, None, "state_key_mapping_audit.csv", "state_table_metric_only_applicable_to_csm"))
            continue
        question = resolver.question(base["question_number"])
        if "state_accuracy" not in set(question.get("applicable_metrics", [])):
            observations.append(observation(base, "state_accuracy", None, False, "state_accuracy_not_applicable_for_question", None, None, "state_key_mapping_audit.csv", "state_accuracy_not_applicable_for_question"))
            continue
        snapshot = snapshots_by_cutoff.get(question.get("source_cutoff"))
        if not snapshot:
            value = None
            reason = "N/A - expected_state_snapshot_missing"
        else:
            state_scores = []
            reason = None
            for expected_state in snapshot.get("states", []):
                matched_states = match_actual_states(expected_state, data["csm_state_trace"])
                component_scores = score_state_components(expected_state, matched_states, resolver)
                score = mean([score for score in component_scores.values() if score is not None])
                state_scores.append(score if score is not None else 0.0)
                audit.append(
                    base
                    | {
                        "expected_snapshot_id": snapshot.get("snapshot_id"),
                        "expected_state": expected_state.get("state_id"),
                        "expected_state_concept": expected_state.get("state_type"),
                        "expected_display_value": expected_state.get("display_value"),
                        "expected_lifecycle_status": expected_state.get("lifecycle_status"),
                        "expected_version": expected_state.get("version"),
                        "expected_valid_period": json.dumps(expected_state.get("valid_period", [])),
                        "expected_review_status": expected_state.get("requires_review"),
                        "expected_evidence_ids": json.dumps(expected_state.get("supporting_evidence_ids", [])),
                        "matched_actual_state": json.dumps([state.get("state_id") for state in matched_states]),
                        "matched_actual_state_key": json.dumps([state.get("state_key") for state in matched_states]),
                        "value_component_score": component_scores["normalized_value"],
                        "unit_component_score": component_scores["unit"],
                        "lifecycle_status_score": component_scores["lifecycle_status"],
                        "validity_interval_score": component_scores["validity_interval"],
                        "version_score": component_scores["version"],
                        "superseded_current_score": component_scores["superseded_current_status"],
                        "review_status_score": component_scores["review_status"],
                        "evidence_lineage_score": component_scores["evidence_lineage"],
                        "component_level_score": score,
                        "calculation_reason": "explicit_expected_state_snapshot_component_mapping",
                    }
                )
            value = mean(state_scores)
        observations.append(observation(base, "state_accuracy", value, value is not None, reason, None, None, "state_key_mapping_audit.csv", reason or "component_state_key_mapping_score"))
    return audit, observations


def build_decision_metrics(data: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    old = [row for row in data["metric_observations"] if row["metric_name"] == "decision_f1"]
    gt_by_question = {
        int(q["question_id"].split("-Q")[-1]): q
        for q in data["ground_truth"]["questions"]
        if q.get("question_id", "").startswith("P1-Q")
    }
    explicit_question_numbers = [
        qn
        for qn, question in gt_by_question.items()
        if question.get("expected_decision_label") in EXPLICIT_DECISION_LABELS
    ]
    insufficient = len(explicit_question_numbers) < 2
    support_by_turn = group(data["claim_support"], "turn_id")
    audit = []
    observations = []
    for row in old:
        base = base_from(row)
        question = gt_by_question.get(int(base["question_number"]), {})
        expected_label = question.get("expected_decision_label")
        generated_labels = extract_decision_labels(" ".join(item.get("claim_text", "") for item in support_by_turn.get(base["turn_id"], [])))
        if expected_label in EXPLICIT_DECISION_LABELS:
            per_turn_f1 = 1.0 if expected_label in generated_labels else 0.0
            reason = "insufficient_decision_ground_truth" if insufficient else None
        else:
            per_turn_f1 = None
            reason = "no_explicit_controlled_ground_truth_decision_label"
        value = None if insufficient else per_turn_f1
        audit.append(
            base
            | {
                "expected_labels": json.dumps([expected_label] if expected_label else []),
                "generated_labels": json.dumps(sorted(generated_labels)),
                "per_turn_decision_f1": per_turn_f1,
                "decision_f1_exported_value": value,
                "explicit_decision_question_count": len(explicit_question_numbers),
                "calculation_reason": reason or "explicit_controlled_label_only",
            }
        )
        observations.append(observation(base, "decision_f1", value, value is not None, reason, 1 if per_turn_f1 == 1.0 else 0 if per_turn_f1 == 0.0 else None, 1 if per_turn_f1 is not None else None, "decision_label_audit.csv", reason or "explicit_ground_truth_controlled_label_f1"))
    return audit, observations


def build_temporal_metrics(data: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    old = [row for row in data["metric_observations"] if row["metric_name"] == "temporal_consistency"]
    matches_by_turn = group(data["claim_matching"], "turn_id")
    audit = []
    observations = []
    for row in old:
        base = base_from(row)
        qn = int(row["question_number"])
        assertions = TEMPORAL_ASSERTIONS.get(qn, [])
        if not assertions:
            reason = "no_explicit_temporal_assertion_ground_truth"
            observations.append(observation(base, "temporal_consistency", None, False, reason, None, None, "temporal_assertion_audit.csv", reason))
            continue
        credited_truth = {
            item.get("matched_ground_truth_claim")
            for item in matches_by_turn.get(base["turn_id"], [])
            if parse_bool(item.get("correctness")) and item.get("matched_ground_truth_claim")
        }
        generated_text = " ".join(item.get("claim_text", "") for item in matches_by_turn.get(base["turn_id"], []))
        correctness_values = []
        for assertion in assertions:
            required = set(assertion["required_truth_claims"])
            has_required = required <= credited_truth
            forbidden_hit = any(term.lower() in generated_text.lower() for term in assertion.get("forbidden_terms", []))
            correct = bool(has_required and not forbidden_hit)
            correctness_values.append(1.0 if correct else 0.0)
            generated_relation = "matched_required_temporal_claims" if has_required else "missing_required_temporal_claims"
            if forbidden_hit:
                generated_relation = "future_or_contradictory_temporal_leakage_detected"
            audit.append(
                base
                | {
                    "assertion_id": assertion["assertion_id"],
                    "event_a": assertion["event_a"],
                    "relation": assertion["relation"],
                    "event_b": assertion["event_b"],
                    "source_cutoff": resolver_source_cutoff(data, qn),
                    "expected_latest_valid_source": assertion["expected_latest_valid_source"],
                    "expected_required_truth_claims": json.dumps(sorted(required)),
                    "generated_relation": generated_relation,
                    "generated_matched_truth_claims": json.dumps(sorted(credited_truth)),
                    "forbidden_terms": json.dumps(assertion.get("forbidden_terms", [])),
                    "correctness": correct,
                    "calculation_reason": "explicit_temporal_assertion_comparison",
                }
            )
        value = mean(correctness_values)
        observations.append(observation(base, "temporal_consistency", value, True, None, sum(correctness_values), len(correctness_values), "temporal_assertion_audit.csv", "explicit_temporal_assertion_comparison"))
    return audit, observations


def build_correction_metrics(data: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    old = [row for row in data["metric_observations"] if row["metric_name"] == "correction_recovery"]
    answer_scores = {
        row["turn_id"]: to_float(row["observation_value"])
        for row in build_answer_f1(data)[1]
        if row["metric_name"] == "answer_accuracy"
    }
    audit = []
    observations = []
    for row in old:
        base = base_from(row)
        qn = int(row["question_number"])
        applicable = qn in CORRECTION_QUESTION_REASONS
        value = answer_scores.get(base["turn_id"]) if applicable else None
        reason = CORRECTION_QUESTION_REASONS.get(qn, "not_correction_dependent_question")
        audit.append(
            base
            | {
                "included": applicable,
                "included_question_numbers": json.dumps(sorted(CORRECTION_QUESTION_REASONS)),
                "inclusion_reason": reason,
                "baseline_question_exclusion_rule": "question_2_excluded_even_if_it_contains_creatinine_or_egfr",
                "scoring_source": "corrected_answer_claim_f1_for_correction_dependent_questions" if applicable else "not_scored",
            }
        )
        observations.append(observation(base, "correction_recovery", value, applicable, reason if not applicable else None, value, 1 if applicable else None, "correction_recovery_audit.csv", reason))
    return audit, observations


def build_faithfulness_metrics(data: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    support_by_turn = group(data["claim_support"], "turn_id")
    audit = []
    observations = []
    for turn_id, rows in support_by_turn.items():
        base = base_from(rows[0])
        factual = [row for row in rows if row.get("support_classification") not in NON_FACTUAL]
        entailed = [row for row in factual if row.get("support_classification") in SUPPORTED]
        for row in factual:
            audit.append(row | {"entailment_classification": "faithful" if row.get("support_classification") in SUPPORTED else "unfaithful", "entailment_reason": row.get("calculation_reason")})
        value = len(entailed) / len(factual) if factual else None
        observations.append(observation(base, "faithfulness", value, bool(factual), "no_factual_claims", len(entailed), len(factual) if factual else None, "faithfulness_entailment_audit.csv", "claim_level_context_entailment_not_citation_validity"))
    return audit, observations


def build_latency_metrics(data: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    old = [row for row in data["metric_observations"] if row["metric_name"] == "p95_latency"]
    audit = []
    observations = []
    for row in old:
        base = base_from(row)
        provider = to_float(row.get("observation_value"))
        retry_backoff = None
        retrieval_activation = None
        total_processing = provider
        wall_clock = None
        audit.append(
            base
            | {
                "provider_generation_latency_ms": provider,
                "retry_backoff_latency_ms": retry_backoff,
                "retry_backoff_latency_status": "not_available_in_v2_or_pilot_latency_exports",
                "retrieval_activation_latency_ms": retrieval_activation,
                "retrieval_activation_latency_status": "not_available_as_separate_duration_in_v2_or_pilot_latency_exports",
                "total_system_processing_latency_ms": total_processing,
                "operational_wall_clock_latency_ms": wall_clock,
                "operational_wall_clock_latency_status": "not_available_in_v2_or_pilot_latency_exports",
                "stored_llm_call_processing_duration_includes_request_delay": "not_indicated_by_export",
                "stored_llm_call_processing_duration_includes_provider_retry_waiting": "not_indicated_by_export",
                "stored_llm_call_processing_duration_includes_retry_after_sleep": "not_indicated_by_export",
                "stored_llm_call_processing_duration_includes_exponential_backoff": "not_indicated_by_export",
                "stored_llm_call_processing_duration_includes_evaluation_time": "not_indicated_by_export",
                "ranking_latency_definition": "provider_generation_latency_excluding_intentional_quota_waits_when_separate_waits_are_available",
            }
        )
        observations.append(observation(base, "p95_latency", provider, provider is not None, "missing_provider_generation_latency", provider, 1, "latency_definition_audit.csv", "provider_generation_latency_excludes_request_delay_retry_after_backoff_when_available"))
    return audit, observations


def build_activation_metrics(data: dict[str, Any], resolver: CanonicalResolver) -> list[dict]:
    old_csm = [row for row in data["metric_observations"] if row["system"] == "csm" and row["metric_name"] == "retrieval_precision"]
    observations = []
    for row in old_csm:
        base = base_from(row)
        question = resolver.question(base["question_number"])
        query = normalize_text(question.get("question_text"))
        selected_canonicals = set()
        selected_rows = 0
        for activation in data["csm_activation"]:
            if normalize_text(activation.get("query_text")) != query or not parse_bool(activation.get("selected")):
                continue
            selected_rows += 1
            for resolved in resolver.resolve(activation.get("state_variable_id")):
                if resolved["resolution_status"] == "resolved":
                    selected_canonicals.add(resolved["canonical_source_id"])
        selected_families = {resolver.family(item) for item in selected_canonicals}
        expected_families = resolver.expected_retrieval_families(base["question_number"])
        relevant_selected = {item for item in selected_canonicals if resolver.family(item) in expected_families}
        satisfied_expected = selected_families & expected_families
        precision = len(relevant_selected) / len(selected_canonicals) if selected_canonicals and expected_families else None
        recall = len(satisfied_expected) / len(expected_families) if selected_canonicals and expected_families else None
        observations.append(observation(base, "activation_precision", precision, precision is not None, "missing_csm_activation_or_expected_ground_truth", len(relevant_selected), len(selected_canonicals) if selected_canonicals else None, "csm_activation_audit.csv", "activated_state_lineage_overlap_over_selected_activated_states"))
        observations.append(observation(base, "activation_recall", recall, recall is not None, "missing_csm_activation_or_expected_ground_truth", len(satisfied_expected), len(expected_families) if expected_families else None, "csm_activation_audit.csv", "activated_state_lineage_overlap_over_expected_evidence"))
    return observations


def replace_observations(old_rows: list[dict], replacements: list[dict]) -> list[dict]:
    replace_keys = {(row["turn_id"], row["metric_name"]) for row in replacements}
    kept = [row for row in old_rows if (row["turn_id"], row["metric_name"]) not in replace_keys and row["metric_name"] not in EXTRA_METRICS]
    return kept + replacements


def aggregate(rows: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["system"], row["metric_name"])].append(row)
    matrix = []
    for system in SYSTEMS:
        for metric in METRICS:
            values = [to_float(row["observation_value"]) for row in grouped.get((system, metric), []) if parse_bool(row["applicable"]) and to_float(row["observation_value"]) is not None]
            ci_low, ci_high = bootstrap_ci(values)
            matrix.append(
                {
                    "patient": "SYN-CSM-001",
                    "questions": 20,
                    "systems": 7,
                    "repetitions": 1,
                    "completed_turns": 140,
                    "system": system,
                    "metric_name": metric,
                    "value": aggregate_value(metric, values),
                    "observation_count": len(values),
                    "total_rows": len(grouped.get((system, metric), [])),
                    "mean": mean(values),
                    "stddev": stddev(values),
                    "median": median(values),
                    "iqr": iqr(values),
                    "min": min(values) if values else None,
                    "max": max(values) if values else None,
                    "ci_low": ci_low,
                    "ci_high": ci_high,
                    "direction": "lower_is_better" if metric in LOWER_IS_BETTER else "higher_is_better",
                    "reason_not_applicable": reasons(grouped.get((system, metric), [])) if not values else None,
                }
            )
    return matrix


def aggregate_value(metric: str, values: list[float]) -> float | None:
    if not values:
        return None
    if metric == "total_cost":
        return sum(values)
    if metric == "p95_latency":
        return percentile(values, 0.95)
    return mean(values)


def rank(matrix: list[dict]) -> list[dict]:
    rows = []
    for metric in METRICS:
        measured = [row for row in matrix if row["metric_name"] == metric and row["value"] is not None]
        measured.sort(key=lambda row: row["value"], reverse=metric not in LOWER_IS_BETTER)
        last = object()
        rank_value = 0
        for index, row in enumerate(measured, start=1):
            if row["value"] != last:
                rank_value = index
                last = row["value"]
            rows.append({"metric_name": metric, "rank": rank_value, "system": row["system"], "value": row["value"], "observation_count": row["observation_count"], "direction": row["direction"]})
    return rows


def paired_stats(rows: list[dict]) -> list[dict]:
    by_key = {}
    for row in rows:
        value = to_float(row.get("observation_value"))
        if parse_bool(row.get("applicable")) and value is not None:
            by_key[(row["system"], row["metric_name"], row["question_id"])] = value
    stats = []
    for metric in METRICS:
        question_ids = {key[2] for key in by_key if key[0] == "csm" and key[1] == metric}
        for system in [item for item in SYSTEMS if item != "csm"]:
            diffs = []
            for question_id in question_ids:
                csm = by_key.get(("csm", metric, question_id))
                other = by_key.get((system, metric, question_id))
                if csm is None or other is None:
                    continue
                diff = csm - other
                if metric in LOWER_IS_BETTER:
                    diff = -diff
                diffs.append(diff)
            ci_low, ci_high = bootstrap_ci(diffs)
            stats.append(
                {
                    "metric_name": metric,
                    "comparison": f"csm_vs_{system}",
                    "paired_sample_count": len(diffs),
                    "mean_difference": mean(diffs),
                    "median_difference": median(diffs),
                    "effect_size": effect_size(diffs),
                    "raw_p_value": sign_test_p(diffs),
                    "adjusted_p_value": None,
                    "ci_low": ci_low,
                    "ci_high": ci_high,
                    "test_result": "computed" if len(diffs) >= 2 else "N/A",
                    "reason": None if len(diffs) >= 2 else "insufficient_paired_observations",
                }
            )
    adjust_p(stats)
    return stats


def compare_old_new(old_matrix: list[dict], new_matrix: list[dict]) -> list[dict]:
    old = {(row["system"], row["metric_name"]): row for row in old_matrix}
    rows = []
    for row in new_matrix:
        old_row = old.get((row["system"], row["metric_name"]), {})
        old_value = to_float(old_row.get("value"))
        new_value = to_float(row.get("value"))
        if row["metric_name"] in AFFECTED_METRICS and (old_value != new_value or old_row.get("observation_count") != str(row.get("observation_count"))):
            rows.append(
                {
                    "system": row["system"],
                    "metric_name": row["metric_name"],
                    "old_value": old_value,
                    "new_value": new_value,
                    "old_observation_count": old_row.get("observation_count"),
                    "new_observation_count": row.get("observation_count"),
                    "change_reason": "v3_final_offline_correction",
                }
            )
    return rows


def verify_export(data: dict[str, Any], rows: list[dict], matrix: list[dict], stats: list[dict]) -> dict[str, Any]:
    errors = []
    turns = {row["turn_id"] for row in rows}
    if len(turns) != 140:
        errors.append(f"turn_count_not_140_found_{len(turns)}")
    if len(rows) < 2940:
        errors.append(f"observation_rows_below_2940_found_{len(rows)}")
    if any(row["metric_name"] == "answer_accuracy" and row["calculation_reason"] != "claim_level_F1" for row in rows):
        errors.append("answer_accuracy_not_f1")
    rag_retrieval = [
        row
        for row in matrix
        if row["metric_name"] in {"retrieval_precision", "retrieval_recall"}
        and row["system"] != "csm"
        and to_float(row.get("value")) not in (None, 0.0)
    ]
    if not rag_retrieval:
        errors.append("rag_retrieval_precision_recall_universally_zero_after_canonicalization")
    if all((row.get("value") in (0, 0.0, None)) for row in matrix if row["metric_name"] == "lineage_citation_f1"):
        if any(row.get("citation_classification") == "valid_supporting" for row in data["citations"]):
            errors.append("lineage_f1_universally_zero_despite_valid_supporting_citations")
    if all(to_float(row.get("value")) == 1.0 for row in matrix if row["metric_name"] == "faithfulness" and row.get("value") not in ("", None)):
        errors.append("faithfulness_universally_one_without_manual_exception")
    decision_values = [row for row in matrix if row["metric_name"] == "decision_f1" and row.get("value") not in ("", None)]
    explicit_decision_count = sum(1 for q in data["ground_truth"]["questions"] if q.get("expected_decision_label") in EXPLICIT_DECISION_LABELS)
    if explicit_decision_count < 2 and decision_values:
        errors.append("decision_f1_reported_despite_insufficient_decision_ground_truth")
    correction_q2 = [
        row
        for row in rows
        if row["metric_name"] == "correction_recovery"
        and row.get("question_number") == "2"
        and parse_bool(row.get("applicable"))
    ]
    if correction_q2:
        errors.append("baseline_question_2_included_in_correction_recovery")
    if any(int(row["paired_sample_count"]) == 1 and row["test_result"] != "N/A" for row in stats):
        errors.append("statistical_comparison_uses_single_aggregate_value")
    return {"status": "passed" if not errors else "failed", "errors": errors, "completed_turns": 140, "metric_observations": len(rows)}


def copy_preserved_files(input_dir: Path, output_dir: Path) -> None:
    for name in ["answer_preservation_audit.json", "claim_support_audit.csv", "citation_resolution_audit.csv", "claims_audit.csv", "citations_audit.csv", "csm_activation_audit.csv", "csm_lineage_trace.json", "csm_state_trace.json"]:
        source = input_dir / name
        if source.exists():
            shutil.copy2(source, output_dir / name)


def expected_canonical_by_turn(data: dict[str, Any]) -> dict[str, set[str]]:
    expected = defaultdict(set)
    for row in data["citations"]:
        if row.get("citation_classification") == "valid_supporting" and row.get("resolved_id"):
            expected[row["turn_id"]].add(row["resolved_id"])
    return expected


def observation(base: dict, metric: str, value: Any, applicable: bool, reason: str | None, numerator: Any, denominator: Any, evidence: str, calculation_reason: str) -> dict:
    return {
        **base,
        "metric_name": metric,
        "observation_value": value,
        "applicable": bool(applicable),
        "reason_not_applicable": None if applicable else reason,
        "numerator": numerator,
        "denominator": denominator,
        "evidence": evidence,
        "calculation_reason": calculation_reason,
    }


def base_from(row: dict) -> dict:
    return {
        "patient": row.get("patient") or "SYN-CSM-001",
        "question_id": row.get("question_id", ""),
        "question_number": row.get("question_number", ""),
        "system": row.get("system", ""),
        "turn_id": row.get("turn_id", ""),
    }


def group(rows: list[dict], key: str) -> dict[str, list[dict]]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row.get(key, "")].append(row)
    return grouped


def question_code(question_number: Any) -> str:
    return f"P1-Q{int(question_number):02d}" if str(question_number).strip() else ""


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def normalize_claim_text(value: Any) -> str:
    text = normalize_text(value)
    text = text.replace("ml/min/1.73m²", "ml/min/1.73m2")
    return re.sub(r"[^a-z0-9./>= -]+", "", text)


def truth_claim_id(question_number: Any, claim: str, prefix: str = "R") -> str:
    digest = hashlib.sha1(normalize_claim_text(claim).encode("utf-8")).hexdigest()[:8]
    return f"{question_code(question_number)}-{prefix}{digest}"


def is_uuid(value: Any) -> bool:
    return bool(re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", str(value or "")))


def extract_benchmark_ids(text: Any) -> list[str]:
    value = str(text or "")
    patterns = [
        r"DOC-P1-\d{3}",
        r"EV-P1-\d{3}",
        r"P1-(?:MEAS|NOTE|ENC|COND|MED|ALL)-\d{3}",
        r"CHAT-P1-\d{3}",
    ]
    found: list[str] = []
    for match in re.finditer("|".join(f"({pattern})" for pattern in patterns), value):
        item = match.group(0)
        if item not in found:
            found.append(item)
    return found


def extract_evidence_ids(text: Any) -> list[str]:
    return [item for item in extract_benchmark_ids(text) if item.startswith("EV-P1-")]


def resolver_source_cutoff(data: dict[str, Any], question_number: int) -> str:
    for question in data["ground_truth"]["questions"]:
        if question.get("question_id") == question_code(question_number):
            return question.get("source_cutoff", "")
    return ""


def extract_decision_labels(text: str) -> set[str]:
    normalized = normalize_text(text).replace("-", " ")
    labels = set()
    if "urgent escalation" in normalized:
        labels.add("urgent_escalation")
    if "clinician review" in normalized or "clinical review" in normalized:
        labels.add("clinician_review")
    if "no follow up" in normalized or "no further follow up" in normalized:
        labels.add("no_follow_up")
    if "pending review" in normalized:
        labels.add("pending_review")
    if "insufficient evidence" in normalized:
        labels.add("insufficient_evidence")
    if "reject" in normalized and ("unverified" in normalized or "unsupported" in normalized):
        labels.add("reject_unverified_claim")
    return labels


def state_payload_text(state: dict[str, Any]) -> str:
    parts = [state.get("state_key"), state.get("state_type"), state.get("status"), state.get("valid_from"), state.get("valid_to")]
    current_value = state.get("current_value", {})
    parts.append(json.dumps(current_value, sort_keys=True, default=str))
    for history in state.get("history", []):
        parts.append(json.dumps(history.get("new_value", {}), sort_keys=True, default=str))
        parts.append(str(history.get("update_reason", "")))
    return normalize_text(" ".join(str(part or "") for part in parts))


def match_actual_states(expected_state: dict[str, Any], actual_states: list[dict[str, Any]]) -> list[dict[str, Any]]:
    state_type = expected_state.get("state_type", "")
    evidence_ids = set(expected_state.get("supporting_evidence_ids", [])) | set(expected_state.get("qualifying_evidence_ids", [])) | set(expected_state.get("contradicting_evidence_ids", []))
    if state_type == "renal_function_trend":
        patterns = ["creatinine", "glomerular", "egfr", "dehydration", "laboratory correction", "renal laboratory", "follow-up laboratory"]
    elif state_type == "renal_medication_review":
        patterns = ["metformin", "lisinopril", "medication", "renal laboratory", "laboratory correction", "follow-up laboratory"]
    else:
        patterns = [state_type.replace("_", " ")]
    matched = []
    for state in actual_states:
        text = state_payload_text(state)
        if any(pattern in text for pattern in patterns) or any(evidence_id.lower() in text for evidence_id in evidence_ids):
            matched.append(state)
    return matched


def score_state_components(expected_state: dict[str, Any], matched_states: list[dict[str, Any]], resolver: CanonicalResolver) -> dict[str, float | None]:
    if not matched_states:
        return {
            "normalized_value": 0.0,
            "unit": 0.0,
            "lifecycle_status": 0.0,
            "validity_interval": 0.0,
            "version": 0.0,
            "superseded_current_status": 0.0,
            "review_status": 0.0,
            "evidence_lineage": 0.0,
        }
    combined = " ".join(state_payload_text(state) for state in matched_states)
    expected_evidence_ids = (
        expected_state.get("supporting_evidence_ids", [])
        + expected_state.get("qualifying_evidence_ids", [])
        + expected_state.get("contradicting_evidence_ids", [])
    )
    expected_families = set()
    for evidence_id in expected_evidence_ids:
        expected_families.add(evidence_id)
        for resolved in resolver.resolve(evidence_id):
            if resolved["resolution_status"] == "resolved":
                expected_families.add(resolved["canonical_family_id"])
    actual_families = set()
    for state in matched_states:
        state_id = state.get("state_id")
        for resolved in resolver.resolve(state_id):
            if resolved["resolution_status"] == "resolved":
                actual_families.add(resolved["canonical_family_id"])
        actual_families.update(extract_benchmark_ids(combined))
    evidence_overlap = expected_families & actual_families
    display = normalize_text(expected_state.get("display_value"))
    value_terms = [term for term in re.split(r"[^a-z0-9.]+", display) if len(term) > 3 or re.search(r"\d", term)]
    value_hits = sum(1 for term in value_terms if term in combined)
    numeric_or_status_hits = 0
    if any(item in combined for item in ["1.0", "86", "1.8", "42", "1.5", "53", "1.2", "70"]):
        numeric_or_status_hits += 1
    if any(item in combined for item in ["baseline", "worsening", "corrected", "dehydration", "improved", "recovery", "review"]):
        numeric_or_status_hits += 1
    value_score = max((value_hits / len(value_terms)) if value_terms else 0.0, min(1.0, numeric_or_status_hits / 2))
    unit_score = 1.0 if any(unit in combined for unit in ["mg/dl", "ml/min", "1.73m2"]) else 0.5
    lifecycle = normalize_text(expected_state.get("lifecycle_status"))
    if lifecycle == "active":
        lifecycle_score = 1.0 if "active" in combined or "final" in combined else 0.5
    elif lifecycle == "candidate":
        lifecycle_score = 1.0 if "candidate" in combined or "review" in combined else 0.5
    elif lifecycle == "contested":
        lifecycle_score = 1.0 if "corrected" in combined and ("superseded" in combined or "dehydration" in combined) else 0.5
    elif lifecycle == "resolved":
        lifecycle_score = 1.0 if "improved" in combined or "near baseline" in combined or "70.0000" in combined else 0.5
    else:
        lifecycle_score = None
    valid_period = expected_state.get("valid_period", [])
    validity_score = 1.0 if valid_period and normalize_text(valid_period[0])[:10] in combined else 0.5
    expected_version = to_float(expected_state.get("version"))
    max_actual_version = max((to_float(state.get("current_version")) or to_float(state.get("version")) or 0.0) for state in matched_states)
    version_score = 1.0 if expected_version and max_actual_version >= expected_version else 0.5
    if expected_state.get("contradicting_evidence_ids"):
        superseded_score = 1.0 if "superseded" in combined or "corrected" in combined else 0.0
    elif lifecycle == "resolved":
        superseded_score = 1.0 if "final" in combined or "near baseline" in combined else 0.5
    else:
        superseded_score = 1.0
    review_expected = bool(expected_state.get("requires_review"))
    review_score = 1.0 if (review_expected and "review" in combined) or (not review_expected and ("routine" in combined or "near baseline" in combined or "baseline" in combined)) else 0.5
    evidence_score = len(evidence_overlap) / len(expected_families) if expected_families else None
    return {
        "normalized_value": value_score,
        "unit": unit_score,
        "lifecycle_status": lifecycle_score,
        "validity_interval": validity_score,
        "version": version_score,
        "superseded_current_status": superseded_score,
        "review_status": review_score,
        "evidence_lineage": evidence_score,
    }


def identifier_type_for(value: Any, key: str | None = None) -> str:
    text = str(value or "")
    if key == "state_id":
        return "csm_state_id"
    if key == "evidence_id":
        return "csm_evidence_id"
    if re.fullmatch(r"[0-9a-fA-F-]{36}", text):
        return "canonical_or_record_uuid"
    if re.match(r"EV-P1-", text):
        return "benchmark_evidence_id"
    if re.match(r"DOC-P1-", text):
        return "benchmark_document_id"
    if re.match(r"P1-(MEAS|NOTE|ENC|COND|MED|ALL|ALLERGY)-", text):
        return "benchmark_source_reference"
    if re.match(r"CHAT-P1-", text):
        return "conversation_source_reference"
    if re.match(r"C\d+", text):
        return "local_citation_alias"
    return "unknown_identifier"


def paper_matrix(matrix: list[dict], metrics: list[str]) -> list[dict]:
    by_key = {(row["system"], row["metric_name"]): row for row in matrix}
    rows = []
    for metric in metrics:
        row = {"metric_name": metric}
        for system in SYSTEMS:
            cell = by_key.get((system, metric), {})
            row[system] = cell.get("value")
            row[f"{system}_n"] = cell.get("observation_count")
        rows.append(row)
    return rows


def paper_summary(validation: dict, rows: list[dict], matrix: list[dict], old_vs_new: list[dict]) -> str:
    return "\n".join(
        [
            "# Sustha Single-Patient Synthetic Case-Study Results",
            "",
            "Patient: SYN-CSM-001",
            "Questions: 20",
            "Systems: 7",
            "Repetitions: 1",
            "Completed turns: 140",
            "",
            f"Metric observations: {len(rows)}",
            f"Affected matrix cells changed: {len(old_vs_new)}",
            "Answer accuracy is claim-level F1 with precision and recall exported separately.",
            "Evidence identifiers are canonicalized before retrieval and lineage scoring where v2 input contains resolvable aliases.",
            "No Groq or provider calls were made; stored answer turns were not modified.",
        ]
    )


def retrieval_sanity_text(audit: list[dict], matrix: list[dict]) -> str:
    nonzero = [row for row in matrix if row["metric_name"] in {"retrieval_precision", "retrieval_recall"} and to_float(row.get("value")) not in (None, 0.0)]
    rag_nonzero = [
        row
        for row in matrix
        if row["metric_name"] in {"retrieval_precision", "retrieval_recall"}
        and row["system"] != "csm"
        and to_float(row.get("value")) not in (None, 0.0)
    ]
    return "\n".join(
        [
            "# Retrieval Manual Sanity Check",
            "",
            f"Resolution audit rows: {len(audit)}",
            f"Non-zero retrieval matrix cells after canonicalization: {len(nonzero)}",
            f"Non-zero RAG retrieval cells after canonicalization: {len(rag_nonzero)}",
            "RAG retrieval uses the original pilot retrieval traces keyed by the preserved turn IDs. Expected benchmark document/source aliases are resolved to canonical source families before comparison.",
            "CSM common retrieval uses selected activated states resolved through state-evidence lineage to canonical sources; activation_precision and activation_recall are exported separately.",
            "The export is rejected if every RAG retrieval precision/recall cell remains zero after canonicalization.",
        ]
    )


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = sorted({key for row in rows for key in row.keys()}) or ["empty"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: serialize(row.get(key)) for key in fields})


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=serialize) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text + "\n", encoding="utf-8")


def serialize(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, sort_keys=True, default=str)
    return value


def parse_bool(value: Any) -> bool:
    return str(value).lower() in {"true", "1", "yes"}


def to_float(value: Any) -> float | None:
    if value in ("", None):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def harmonic(precision: float | None, recall: float | None) -> float | None:
    if precision is None or recall is None:
        return None
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def stddev(values: list[float]) -> float | None:
    return statistics.stdev(values) if len(values) > 1 else (0.0 if values else None)


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * p
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def iqr(values: list[float]) -> float | None:
    if not values:
        return None
    return (percentile(values, 0.75) or 0.0) - (percentile(values, 0.25) or 0.0)


def bootstrap_ci(values: list[float], samples: int = 500) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    if len(values) == 1:
        return values[0], values[0]
    rng = random.Random(20260722)
    means = []
    for _ in range(samples):
        sample = [values[rng.randrange(len(values))] for _ in values]
        means.append(sum(sample) / len(sample))
    return percentile(means, 0.025), percentile(means, 0.975)


def effect_size(values: list[float]) -> float | None:
    sd = stddev(values)
    return None if not sd else (mean(values) or 0.0) / sd


def sign_test_p(values: list[float]) -> float | None:
    positives = sum(1 for value in values if value > 0)
    negatives = sum(1 for value in values if value < 0)
    n = positives + negatives
    if n < 2:
        return None
    k = min(positives, negatives)
    return min(1.0, 2 * sum(math.comb(n, i) * (0.5**n) for i in range(k + 1)))


def adjust_p(rows: list[dict]) -> None:
    p_rows = [row for row in rows if row["raw_p_value"] is not None]
    total = len(p_rows)
    for index, row in enumerate(sorted(p_rows, key=lambda item: item["raw_p_value"]), start=1):
        row["adjusted_p_value"] = min(1.0, row["raw_p_value"] * total / index)


def reasons(rows: list[dict]) -> str | None:
    values = sorted({row.get("reason_not_applicable") for row in rows if row.get("reason_not_applicable")})
    return "; ".join(values) if values else None


def parse_jsonish(value: str) -> Any:
    if not value:
        return {}
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {}


if __name__ == "__main__":
    raise SystemExit(main())
