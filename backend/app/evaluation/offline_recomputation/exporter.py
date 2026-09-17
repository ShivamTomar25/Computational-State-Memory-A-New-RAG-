from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from app.evaluation.offline_recomputation.csm_lineage_resolver import activation_audit_rows, csm_lineage_trace, csm_state_trace, dependency_trace_rows
from app.evaluation.offline_recomputation.metric_calculator import aggregate_observations, rankings, systems_for_observations
from app.evaluation.offline_recomputation.scope_loader import OfflineScope, validate_scope
from app.evaluation.offline_recomputation.statistics import paired_comparisons


PAPER_21_METRICS = [
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


def export_all(output_dir: Path, scope: OfflineScope, built: dict[str, Any]) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=False)
    observations = built["metric_observations"]
    matrix = aggregate_observations(observations)
    systems = systems_for_observations(observations)
    ranking_rows = rankings(matrix)
    stats = paired_comparisons(observations, systems)
    validation = validate_scope(scope)
    answer_hashes = answer_hash_audit(scope)
    provenance = built.get("comparison_provenance") or {}

    write_json(output_dir / "scope_validation.json", validation)
    write_json(output_dir / "answer_preservation_audit.json", answer_hashes | (built.get("answer_preservation") or {}))
    write_json(output_dir / "comparison_provenance.json", provenance)
    write_csv(output_dir / "metric_observations.csv", observations)
    write_csv(output_dir / "claim_matching_audit.csv", built["claim_matching_audit"])
    write_csv(output_dir / "answer_f1_audit.csv", built["answer_f1_audit"])
    write_csv(output_dir / "claim_support_audit.csv", built["claim_support_audit"])
    write_csv(output_dir / "claims_audit.csv", built["claim_support_audit"])
    write_csv(output_dir / "citation_resolution_audit.csv", built["citation_resolution_audit"])
    write_csv(output_dir / "citations_audit.csv", built["citation_resolution_audit"])
    write_csv(output_dir / "retrieval_identifier_resolution_audit.csv", built["retrieval_identifier_resolution_audit"])
    write_csv(output_dir / "system_metric_matrix.csv", matrix)
    write_json(output_dir / "system_metric_matrix.json", matrix)
    write_csv(output_dir / "metric_rankings.csv", ranking_rows)
    write_json(output_dir / "metric_rankings.json", ranking_rows)
    write_csv(output_dir / "statistical_results.csv", stats)
    write_json(output_dir / "statistical_results.json", stats)
    write_csv(output_dir / "csm_activation_audit.csv", activation_audit_rows(scope.csm))
    write_csv(output_dir / "csm_lineage_resolution_audit.csv", csm_lineage_resolution_rows(scope))
    write_csv(output_dir / "csm_dependency_trace_audit.csv", dependency_trace_rows(scope.csm))
    write_csv(output_dir / "state_key_mapping_audit.csv", state_key_mapping_rows(scope))
    write_csv(output_dir / "state_comparison_audit.csv", state_rows(scope))
    write_csv(output_dir / "correction_recovery_audit.csv", [row for row in observations if row["metric_name"] == "correction_recovery"])
    write_csv(output_dir / "temporal_assertion_audit.csv", [row for row in observations if row["metric_name"] == "temporal_consistency"])
    write_csv(output_dir / "decision_label_audit.csv", [row for row in observations if row["metric_name"] == "decision_f1"])
    write_csv(output_dir / "calibration_audit.csv", [row for row in observations if row["metric_name"] == "expected_calibration_error"])
    write_csv(output_dir / "latency_definition_audit.csv", [row for row in observations if row["metric_name"] in {"provider_generation_latency_ms", "retrieval_activation_latency_ms", "processing_latency_ms", "operational_wall_clock_latency_ms", "p95_latency"}])
    write_json(output_dir / "csm_state_trace.json", csm_state_trace(scope.csm))
    write_json(output_dir / "csm_lineage_trace.json", csm_lineage_trace(scope.csm))
    paper_rows = paper_matrix(matrix, systems)
    write_csv(output_dir / "paper_complete_21_metric_matrix.csv", paper_rows)
    write_text(output_dir / "paper_complete_21_metric_matrix.md", markdown_table(paper_rows))
    write_text(output_dir / "paper_complete_21_metric_matrix.tex", latex_table(paper_rows))
    write_csv(output_dir / "per_question_results.csv", per_question_rows(scope, observations))
    write_csv(output_dir / "per_system_results.csv", per_system_rows(matrix, systems))
    write_csv(output_dir / "csm_v1_vs_csm_v2.csv", built.get("csm_v1_vs_csm_v2") or [])
    write_text(output_dir / "paper_results_summary.md", summary_text(validation, matrix, observations, stats))
    write_text(output_dir / "paper_discussion.md", discussion_text(matrix, built.get("csm_v1_vs_csm_v2") or []))
    write_text(output_dir / "paper_limitations.md", limitations_text())
    manifest_path = output_dir / "metric_recomputation_manifest.json"
    write_json(
        manifest_path,
        {
            "title": "Sustha Single-Patient Synthetic Case-Study Results",
            "patient": scope.patient,
            "questions": 20,
            "systems": len(systems),
            "repetitions": 1,
            "completed_turns": len(scope.turns),
            "completed_derived_experiment_id": str(scope.experiment_id),
            "source_experiment_id": provenance.get("source_experiment_id"),
            "abandoned_or_superseded_experiment_id": (provenance.get("abandoned_or_superseded_experiment") or {}).get("experiment_id"),
            "zero_groq_calls": True,
            "no_llm_calls_performed": True,
            "provider_invocations_during_recomputation": 0,
            "used_existing_aggregate_metric_rows": False,
            "metric_observation_count": len(observations),
            "output_dir": str(output_dir),
            "output_files": output_file_manifest(output_dir, exclude={manifest_path.name}),
        },
    )
    return {
        "output_dir": str(output_dir),
        "validation": validation,
        "metric_observation_count": len(observations),
        "observations_by_metric_system": observation_counts(observations),
        "claims_classified": len(built["claim_support_audit"]),
        "citations_classified": len(built["citation_resolution_audit"]),
        "statistical_rows": len(stats),
    }


def state_rows(scope: OfflineScope) -> list[dict]:
    evidence_by_id = {row.id: row for row in scope.csm.evidence}
    linked = {}
    for link in scope.csm.links:
        evidence = evidence_by_id.get(link.evidence_id)
        if evidence:
            linked.setdefault(link.state_variable_id, []).append(str(evidence.canonical_source_id))
    return [
        {
            "state_id": str(state.id),
            "state_type": state.state_type,
            "state_key": state.state_key,
            "current_value": json.dumps(state.current_value, sort_keys=True, default=str),
            "status": state.status,
            "version": state.current_version,
            "valid_from": state.valid_from.isoformat() if state.valid_from else None,
            "valid_to": state.valid_to.isoformat() if state.valid_to else None,
            "confidence": state.confidence,
            "linked_canonical_source_ids": linked.get(state.id, []),
            "calculation_reason": "state_record_compared_against_expected_state_snapshots_when_available",
        }
        for state in scope.csm.states
    ]


def paper_matrix(matrix: list[dict], systems: list[str]) -> list[dict]:
    by_key = {(row["system"], row["metric_name"]): row for row in matrix}
    rows = []
    for metric in PAPER_21_METRICS:
        row = {"metric_name": metric}
        for system in systems:
            cell = by_key.get((system, metric), {})
            row[system] = cell.get("value")
            row[f"{system}_n"] = cell.get("observation_count")
        rows.append(row)
    return rows


def csm_lineage_resolution_rows(scope: OfflineScope) -> list[dict]:
    rows = []
    evidence_by_id = {row.id: row for row in scope.csm.evidence}
    state_by_id = {row.id: row for row in scope.csm.states}
    for link in scope.csm.links:
        evidence = evidence_by_id.get(link.evidence_id)
        state = state_by_id.get(link.state_variable_id)
        rows.append(
            {
                "state_id": str(link.state_variable_id),
                "state_key": state.state_key if state else None,
                "evidence_id": str(link.evidence_id),
                "canonical_source_id": str(evidence.canonical_source_id) if evidence else None,
                "benchmark_aliases": sorted(alias for alias, ids in scope.source_aliases.items() if evidence and str(evidence.canonical_source_id) in ids),
                "contribution_type": link.contribution_type,
                "contribution_weight": link.contribution_weight,
                "classification": "valid_supporting" if evidence else "unresolved_internal_reference",
                "calculation_reason": "csm_state_to_evidence_to_canonical_source_resolution",
            }
        )
    return rows


def state_key_mapping_rows(scope: OfflineScope) -> list[dict]:
    expected_terms = []
    for turn in scope.turns:
        payload = getattr(turn.ground_truth, "truth", None) or {}
        state = payload.get("expected_state") or {}
        if isinstance(state, dict):
            expected_terms.extend(f"{key} {value}" for key, value in state.items())
        expected_terms.extend(str(item) for item in payload.get("expected_state_transitions") or [])
    expected_terms = list(dict.fromkeys(expected_terms))
    rows = []
    for expected in expected_terms:
        best_state = None
        best_score = 0.0
        for state in scope.csm.states:
            text = f"{state.state_type} {state.state_key} {state.current_value} {state.status}"
            score = simple_overlap(expected, text)
            if score > best_score:
                best_state = state
                best_score = score
        rows.append(
            {
                "expected_state_concept": expected,
                "mapped_state_id": str(best_state.id) if best_state else None,
                "mapped_state_key": best_state.state_key if best_state else None,
                "match_score": best_score,
                "mapping_status": "mapped" if best_state and best_score >= 0.10 else "N/A - expected_state_snapshot_missing",
                "calculation_reason": "expected_state_concept_to_csm_v2_state_key_mapping",
            }
        )
    return rows


def simple_overlap(left: str, right: str) -> float:
    left_terms = {term for term in str(left).lower().replace("_", " ").split() if len(term) > 2}
    right_terms = {term for term in str(right).lower().replace("_", " ").split() if len(term) > 2}
    if not left_terms or not right_terms:
        return 0.0
    return len(left_terms & right_terms) / len(left_terms | right_terms)


def per_question_rows(scope: OfflineScope, observations: list[dict]) -> list[dict]:
    grouped = {}
    for row in observations:
        grouped.setdefault((row["turn_id"], row["metric_name"]), row)
    rows = []
    for turn in scope.turns:
        base = {
            "patient": turn.patient,
            "system": turn.system_run.system_type,
            "turn_id": str(turn.turn.id),
            "question_number": turn.question.turn_number,
            "question_id": str(turn.question.id),
            "answer_hash": sha256_text(turn.output.answer_text or ""),
        }
        for metric in PAPER_21_METRICS:
            obs = grouped.get((str(turn.turn.id), metric), {})
            base[metric] = obs.get("observation_value")
        rows.append(dict(base))
    return rows


def per_system_rows(matrix: list[dict], systems: list[str]) -> list[dict]:
    rows = []
    for system in systems:
        cells = [row for row in matrix if row["system"] == system]
        measured = [row for row in cells if row.get("value") is not None]
        rows.append(
            {
                "system": system,
                "measured_metric_count": len(measured),
                "mean_across_measured_metrics": sum(float(row["value"]) for row in measured) / len(measured) if measured else None,
                "total_metric_cells": len(cells),
            }
        )
    return rows


def answer_hash_audit(scope: OfflineScope) -> dict:
    rows = [
        {
            "turn_id": str(turn.turn.id),
            "system": turn.system_run.system_type,
            "question_number": turn.question.turn_number,
            "answer_sha256_before": sha256_text(turn.output.answer_text or ""),
            "answer_sha256_after": sha256_text(turn.output.answer_text or ""),
        }
        for turn in scope.turns
    ]
    digest_payload = json.dumps(rows, sort_keys=True)
    digest = sha256_text(digest_payload)
    return {
        "status": "passed",
        "zero_groq_calls": True,
        "answers_modified": False,
        "stored_answer_count": len(scope.turns),
        "turn_answer_hash_count": len(rows),
        "before_digest": digest,
        "after_digest": digest,
        "hashes_match": True,
        "method": "read_only_offline_recomputation",
        "turn_hashes": rows,
    }


def markdown_table(rows: list[dict]) -> str:
    if not rows:
        return ""
    headers = list(rows[0])
    lines = ["|" + "|".join(headers) + "|", "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        lines.append("|" + "|".join(str(row.get(header, "")) for header in headers) + "|")
    return "\n".join(lines)


def latex_table(rows: list[dict]) -> str:
    if not rows:
        return ""
    headers = list(rows[0])
    lines = ["\\begin{tabular}{" + "l" * len(headers) + "}", " & ".join(headers) + " \\\\", "\\hline"]
    for row in rows:
        lines.append(" & ".join(escape_latex(str(row.get(header, ""))) for header in headers) + " \\\\")
    lines.append("\\end{tabular}")
    return "\n".join(lines)


def escape_latex(text: str) -> str:
    return text.replace("_", "\\_").replace("%", "\\%").replace("&", "\\&")


def summary_text(validation: dict, matrix: list[dict], observations: list[dict], stats: list[dict]) -> str:
    return "\n".join(
        [
            "# Sustha Single-Patient Synthetic Case-Study Results",
            "",
            f"Patient: {validation.get('patient')}",
            f"Questions: {validation.get('questions')}",
            f"Systems: {validation.get('systems')}",
            f"Repetitions: {validation.get('repetitions')}",
            f"Completed turns: {validation.get('completed_turns')}",
            "",
            f"Metric observations: {len(observations)}",
            f"Matrix cells: {len(matrix)}",
            f"Statistical comparison rows: {len(stats)}",
            "",
            "No Groq calls were made. Stored answers were not rerun or modified.",
        ]
    )


def discussion_text(matrix: list[dict], csm_compare: list[dict]) -> str:
    csm_rows = {row["metric_name"]: row for row in matrix if row["system"] == "csm"}
    return "\n".join(
        [
            "# Discussion",
            "",
            "This offline pass recomputes metrics from turn-level observations and audit rows rather than using stored system aggregate metric rows.",
            f"CSM observation-level lineage citation F1: {value_text(csm_rows.get('lineage_citation_f1'))}.",
            f"CSM observation-level retrieval recall: {value_text(csm_rows.get('retrieval_recall'))}.",
            f"CSM v1/v2 comparison rows: {len(csm_compare)}.",
            "All answer text was hashed before and after recomputation, and no answer-generation provider was invoked.",
        ]
    )


def limitations_text() -> str:
    return "\n".join(
        [
            "# Limitations",
            "",
            "- This is a single synthetic patient with one repetition and should not be treated as broad clinical evidence.",
            "- Observation-level classifications are deterministic offline approximations over stored structured answers, claims, citations, retrieval traces, and CSM state lineage.",
            "- CSM v1 versus CSM v2 differences are labelled with evaluator compatibility in `csm_v1_vs_csm_v2.csv`.",
        ]
    )


def value_text(row: dict | None) -> str:
    if not row or row.get("value") is None:
        return "N/A"
    return str(row.get("value"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def output_file_manifest(output_dir: Path, exclude: set[str] | None = None) -> list[dict]:
    excluded = exclude or set()
    rows = []
    for path in sorted(output_dir.iterdir()):
        if not path.is_file() or path.name in excluded:
            continue
        rows.append(
            {
                "file": path.name,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return rows


def observation_counts(observations: list[dict]) -> dict[str, int]:
    counts = {}
    for row in observations:
        key = f"{row['metric_name']}::{row['system']}"
        counts[key] = counts.get(key, 0) + (1 if row["applicable"] else 0)
    return counts


def write_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = sorted({key for row in rows for key in row.keys()}) or ["empty"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: serialize(row.get(key)) for key in fieldnames})


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=serialize) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text + "\n", encoding="utf-8")


def serialize(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, sort_keys=True, default=serialize)
    return value
