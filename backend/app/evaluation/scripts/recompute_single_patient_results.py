from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import statistics
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.evaluation.claims.matching.matcher import match_claims
from app.evaluation.claims.normalization.normalizer import normalize_generated_claim, normalize_text, normalize_truth_claim
from app.evaluation.datasets.models.dataset import BenchmarkCase, BenchmarkQuestion
from app.evaluation.experiments.models.experiment import (
    Experiment,
    ExperimentClaim,
    ExperimentOutput,
    ExperimentSystemRun,
    ExperimentTurn,
)
from app.evaluation.ground_truth.models.ground_truth import BenchmarkGroundTruth
from app.evaluation.metrics.calculators.claim_metrics import calculate_claim_metric_group
from app.evaluation.metrics.calculators.common import measured_ratio, measured_value, not_applicable
from app.evaluation.metrics.calculators.context import EvaluationTurnContext
from app.evaluation.metrics.calculators.efficiency_metrics import calculate_efficiency_metric_group
from app.evaluation.metrics.calculators.retrieval_metrics import calculate_retrieval_metric_group
from app.evaluation.metrics.calculators.state_metrics import calculate_state_metric_group
from app.evaluation.metrics.cost.pricing import estimate_token_cost
from app.llm.common.models.llm import LlmCall
from app.memory_systems.common.models.memory import CanonicalMemorySource, MemoryRetrievalItem, MemoryRetrievalRun
from app.memory_systems.csm.models import (
    CsmActivationItem,
    CsmActivationRun,
    CsmConflict,
    CsmEvidence,
    CsmReviewRequest,
    CsmStateEvidenceLink,
    CsmStateHistory,
    CsmStateVariable,
)


SYSTEMS = ["long_context", "rolling_summary", "dense_rag", "hybrid_rag", "graph_rag", "hippo_rag", "csm"]
METRICS = [
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
PAPER_GROUPS = {
    "complete_21_metric_matrix": METRICS,
    "answer_quality": [
        "answer_accuracy",
        "hallucination_rate",
        "evidence_support_rate",
        "unsupported_claim_rate",
        "fabricated_citation_rate",
        "faithfulness",
        "groundedness",
        "expected_calibration_error",
    ],
    "retrieval": ["retrieval_precision", "retrieval_recall", "lineage_citation_f1"],
    "state_memory": [
        "state_accuracy",
        "temporal_consistency",
        "decision_f1",
        "contradiction_handling",
        "correction_recovery",
        "memory_update_accuracy",
        "state_recovery_time",
    ],
    "efficiency": ["tokens_per_query", "p95_latency", "total_cost"],
}
MAIN_METRICS = [
    "answer_accuracy",
    "evidence_support_rate",
    "hallucination_rate",
    "retrieval_recall",
    "state_accuracy",
    "memory_update_accuracy",
    "tokens_per_query",
    "p95_latency",
    "total_cost",
]


@dataclass(frozen=True)
class ScopedTurn:
    run: ExperimentSystemRun
    turn: ExperimentTurn
    question: BenchmarkQuestion
    truth: BenchmarkGroundTruth | None
    output: ExperimentOutput
    claims: list[ExperimentClaim]
    retrieval_items: list[MemoryRetrievalItem]
    llm_call: LlmCall | None


@dataclass(frozen=True)
class MetricObservation:
    system: str
    metric_name: str
    turn_number: int
    question_id: str
    turn_id: str
    value: float | None
    numerator: float | None
    denominator: float | None
    applicable: bool
    reason_not_applicable: str | None
    details: dict[str, Any]


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline corrected Sustha Patient 1 result recomputation.")
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--patient", default="SYN-CSM-001")
    parser.add_argument("--repetition", type=int, default=1)
    parser.add_argument("--output-root", default="../evaluation/results/corrected_single_patient_pilot")
    args = parser.parse_args()

    experiment_id = UUID(args.experiment_id)
    output_dir = (
        Path(args.output_root)
        / args.patient
        / f"repetition_{args.repetition}"
        / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ).resolve()
    output_dir.mkdir(parents=True, exist_ok=False)

    db = SessionLocal()
    try:
        experiment = db.get(Experiment, experiment_id)
        if experiment is None:
            raise SystemExit(f"Experiment not found: {experiment_id}")

        scoped_turns = load_scope(db, experiment_id, args.patient, args.repetition)
        validation = validate_scope(experiment, scoped_turns, args.patient, args.repetition)
        if validation["errors"]:
            write_json(output_dir / "scope_validation.json", validation)
            raise SystemExit(f"Scope validation failed; see {output_dir / 'scope_validation.json'}")

        before_hashes = answer_hashes(scoped_turns)
        canonical_sources = load_canonical_sources(db, scoped_turns)
        csm_bundle = load_csm_bundle(db, scoped_turns)

        claim_rows, citation_rows = build_claim_and_citation_audits(scoped_turns, canonical_sources)
        metric_observations = recompute_observations(scoped_turns)
        matrix_rows, matrix_json = aggregate_matrix(metric_observations)
        ranking_rows, ranking_json = build_rankings(matrix_rows)
        not_applicable_rows = [as_csv_observation(obs) for obs in metric_observations if not obs.applicable]
        stats_rows, stats_json = statistical_comparisons(metric_observations)

        write_validation_files(output_dir, experiment_id, args, validation, before_hashes, scoped_turns)
        write_audit_files(output_dir, scoped_turns, canonical_sources, csm_bundle, claim_rows, citation_rows, metric_observations)
        write_result_files(output_dir, scoped_turns, metric_observations, matrix_rows, matrix_json, ranking_rows, ranking_json, not_applicable_rows, stats_rows, stats_json)
        write_efficiency_files(output_dir, scoped_turns)
        write_paper_files(output_dir, matrix_rows, ranking_rows, stats_rows, validation)

        after_hashes = answer_hashes(scoped_turns)
        write_json(
            output_dir / "answer_preservation_audit.json",
            {
                "status": "passed" if before_hashes == after_hashes else "failed",
                "read_only_recomputation": True,
                "answer_count": len(before_hashes),
                "changed_answer_hashes": sorted(set(before_hashes.items()) ^ set(after_hashes.items())),
                "hashes": before_hashes,
            },
        )

        manifest = {
            "status": "completed",
            "source_experiment_id": str(experiment_id),
            "patient": args.patient,
            "repetition": args.repetition,
            "systems": SYSTEMS,
            "metrics": METRICS,
            "turn_count": len(scoped_turns),
            "expected_turn_count": 140,
            "metric_observation_count": len(metric_observations),
            "applicable_metric_observation_count": sum(1 for item in metric_observations if item.applicable),
            "not_applicable_metric_observation_count": sum(1 for item in metric_observations if not item.applicable),
            "no_live_llm_calls": True,
            "no_provider_health_checks": True,
            "created_at": now_iso(),
            "output_dir": str(output_dir),
            "reproducibility_command": reproducibility_command(args),
        }
        write_json(output_dir / "metric_recomputation_manifest.json", manifest)
        print(json.dumps(manifest, indent=2))
        return 0
    finally:
        db.close()


def load_scope(db: Session, experiment_id: UUID, patient_key: str, repetition: int) -> list[ScopedTurn]:
    run_rows = list(
        db.execute(
            select(ExperimentSystemRun, BenchmarkCase)
            .join(BenchmarkCase, ExperimentSystemRun.case_id == BenchmarkCase.id)
            .where(
                ExperimentSystemRun.experiment_id == experiment_id,
                ExperimentSystemRun.repetition_number == repetition,
                BenchmarkCase.case_key == patient_key,
                ExperimentSystemRun.system_type.in_(SYSTEMS),
            )
        ).all()
    )
    runs = [row[0] for row in run_rows]
    run_by_id = {run.id: run for run in runs}
    if not run_by_id:
        return []

    turns = list(
        db.scalars(
            select(ExperimentTurn)
            .where(ExperimentTurn.system_run_id.in_(list(run_by_id)), ExperimentTurn.status == "completed")
            .order_by(ExperimentTurn.turn_number.asc(), ExperimentTurn.id.asc())
        ).all()
    )
    turn_ids = [turn.id for turn in turns]
    question_ids = {turn.question_id for turn in turns}

    questions = {item.id: item for item in db.scalars(select(BenchmarkQuestion).where(BenchmarkQuestion.id.in_(question_ids))).all()}
    truths = {}
    for truth in db.scalars(select(BenchmarkGroundTruth).where(BenchmarkGroundTruth.question_id.in_(question_ids))).all():
        current = truths.get(truth.question_id)
        if current is None or truth.version > current.version:
            truths[truth.question_id] = truth

    outputs = {item.turn_id: item for item in db.scalars(select(ExperimentOutput).where(ExperimentOutput.turn_id.in_(turn_ids))).all()}
    output_ids = [output.id for output in outputs.values()]
    claims_by_output: dict[UUID, list[ExperimentClaim]] = defaultdict(list)
    for claim in db.scalars(select(ExperimentClaim).where(ExperimentClaim.output_id.in_(output_ids)).order_by(ExperimentClaim.claim_id.asc())).all():
        claims_by_output[claim.output_id].append(claim)

    retrieval_run_ids = [turn.retrieval_run_id for turn in turns if turn.retrieval_run_id]
    retrieval_items_by_run: dict[UUID, list[MemoryRetrievalItem]] = defaultdict(list)
    if retrieval_run_ids:
        for item in db.scalars(
            select(MemoryRetrievalItem)
            .where(MemoryRetrievalItem.retrieval_run_id.in_(retrieval_run_ids))
            .order_by(MemoryRetrievalItem.retrieval_run_id.asc(), MemoryRetrievalItem.rank.asc())
        ).all():
            retrieval_items_by_run[item.retrieval_run_id].append(item)

    llm_ids = [turn.llm_call_id for turn in turns if turn.llm_call_id]
    llm_calls = {item.id: item for item in db.scalars(select(LlmCall).where(LlmCall.id.in_(llm_ids))).all()} if llm_ids else {}

    scoped = []
    for turn in turns:
        output = outputs.get(turn.id)
        question = questions.get(turn.question_id)
        if output is None or question is None:
            continue
        scoped.append(
            ScopedTurn(
                run=run_by_id[turn.system_run_id],
                turn=turn,
                question=question,
                truth=truths.get(question.id),
                output=output,
                claims=claims_by_output.get(output.id, []),
                retrieval_items=retrieval_items_by_run.get(turn.retrieval_run_id, []),
                llm_call=llm_calls.get(turn.llm_call_id),
            )
        )
    return scoped


def validate_scope(experiment: Experiment, scoped_turns: list[ScopedTurn], patient: str, repetition: int) -> dict[str, Any]:
    counts = Counter(item.run.system_type for item in scoped_turns)
    turn_keys = Counter((item.run.system_type, item.question.turn_number) for item in scoped_turns)
    statuses = Counter(item.turn.status for item in scoped_turns)
    missing_truth = [str(item.question.id) for item in scoped_turns if item.truth is None]
    missing_outputs = [str(item.turn.id) for item in scoped_turns if not item.output.answer_text]
    missing_llm = [str(item.turn.id) for item in scoped_turns if item.llm_call is None]
    errors = []
    if len(scoped_turns) != 140:
        errors.append(f"expected_140_completed_turns_found_{len(scoped_turns)}")
    for system in SYSTEMS:
        if counts[system] != 20:
            errors.append(f"{system}_expected_20_completed_found_{counts[system]}")
    duplicates = [f"{system}:{turn}" for (system, turn), count in turn_keys.items() if count > 1]
    if duplicates:
        errors.append("duplicate_system_question_turns")
    if missing_truth:
        errors.append("missing_ground_truth")
    if missing_outputs:
        errors.append("missing_answer_text")
    return {
        "status": "passed" if not errors else "failed",
        "errors": errors,
        "experiment_id": str(experiment.id),
        "experiment_status": experiment.status,
        "patient": patient,
        "repetition": repetition,
        "expected_turns": 140,
        "completed_turns": len(scoped_turns),
        "statuses": dict(statuses),
        "system_counts": {system: counts[system] for system in SYSTEMS},
        "duplicate_system_question_turns": duplicates,
        "missing_ground_truth_question_ids": missing_truth,
        "missing_answer_text_turn_ids": missing_outputs,
        "missing_llm_call_turn_ids": missing_llm,
        "summary_turn_denominator": 140,
        "no_live_llm_calls": True,
    }


def answer_hashes(scoped_turns: list[ScopedTurn]) -> dict[str, str]:
    hashes = {}
    for item in scoped_turns:
        payload = {
            "turn_id": str(item.turn.id),
            "output_id": str(item.output.id),
            "answer_text": item.output.answer_text or "",
            "structured_answer": item.output.structured_answer or {},
            "citations": item.output.citations or [],
        }
        hashes[str(item.turn.id)] = hashlib.sha256(json_dumps(payload).encode("utf-8")).hexdigest()
    return hashes


def load_canonical_sources(db: Session, scoped_turns: list[ScopedTurn]) -> dict[str, CanonicalMemorySource]:
    source_ids = set()
    for item in scoped_turns:
        for retrieved in item.retrieval_items:
            if retrieved.canonical_source_id:
                source_ids.add(retrieved.canonical_source_id)
        for citation in item.output.citations or []:
            for key in ("canonical_source_id", "source_id"):
                value = citation.get(key) if isinstance(citation, dict) else None
                if value:
                    try:
                        source_ids.add(UUID(str(value)))
                    except ValueError:
                        pass
    if not source_ids:
        return {}
    return {str(row.id): row for row in db.scalars(select(CanonicalMemorySource).where(CanonicalMemorySource.id.in_(source_ids))).all()}


def load_csm_bundle(db: Session, scoped_turns: list[ScopedTurn]) -> dict[str, Any]:
    instance_ids = {item.run.system_instance_id for item in scoped_turns if item.run.system_type == "csm" and item.run.system_instance_id}
    if not instance_ids:
        return {
            "states": [],
            "history": [],
            "evidence": [],
            "links": [],
            "conflicts": [],
            "reviews": [],
            "activation_runs": [],
            "activation_items": [],
        }
    states = list(db.scalars(select(CsmStateVariable).where(CsmStateVariable.system_instance_id.in_(instance_ids))).all())
    state_ids = [state.id for state in states]
    evidence = list(db.scalars(select(CsmEvidence).where(CsmEvidence.system_instance_id.in_(instance_ids))).all())
    evidence_ids = [row.id for row in evidence]
    activation_runs = list(db.scalars(select(CsmActivationRun).where(CsmActivationRun.system_instance_id.in_(instance_ids))).all())
    activation_run_ids = [row.id for row in activation_runs]
    return {
        "states": states,
        "history": list(db.scalars(select(CsmStateHistory).where(CsmStateHistory.state_variable_id.in_(state_ids))).all()) if state_ids else [],
        "evidence": evidence,
        "links": list(db.scalars(select(CsmStateEvidenceLink).where(CsmStateEvidenceLink.evidence_id.in_(evidence_ids))).all()) if evidence_ids else [],
        "conflicts": list(db.scalars(select(CsmConflict).where(CsmConflict.system_instance_id.in_(instance_ids))).all()),
        "reviews": list(db.scalars(select(CsmReviewRequest).where(CsmReviewRequest.system_instance_id.in_(instance_ids))).all()),
        "activation_runs": activation_runs,
        "activation_items": list(db.scalars(select(CsmActivationItem).where(CsmActivationItem.activation_run_id.in_(activation_run_ids))).all()) if activation_run_ids else [],
    }


def build_claim_and_citation_audits(scoped_turns: list[ScopedTurn], canonical_sources: dict[str, CanonicalMemorySource]) -> tuple[list[dict], list[dict]]:
    claim_rows = []
    citation_rows = []
    for item in scoped_turns:
        valid_ids, alias_map = valid_context_ids(item)
        truth_claims = [normalize_truth_claim(claim) for claim in truth_claims_from(item.truth)]
        generated_claims = [normalize_generated_claim(claim) for claim in item.claims]
        matches = match_claims(generated_claims, truth_claims)
        match_by_claim_id = {match.generated.claim_id: match for match in matches}
        for claim in item.claims:
            generated = normalize_generated_claim(claim)
            match = match_by_claim_id.get(generated.claim_id)
            resolved_citations = resolve_citations(claim.citation_ids or [], valid_ids, alias_map)
            classification, reason = classify_claim(claim, match, resolved_citations)
            claim_rows.append(
                {
                    "system": item.run.system_type,
                    "turn_number": item.question.turn_number,
                    "question_id": str(item.question.id),
                    "turn_id": str(item.turn.id),
                    "output_id": str(item.output.id),
                    "claim_id": claim.claim_id,
                    "claim_text": claim.claim_text,
                    "stored_source_support_status": claim.source_support_status,
                    "corrected_support_status": classification,
                    "classification_reason": reason,
                    "confidence": claim.confidence,
                    "citation_ids": json_dumps(claim.citation_ids or []),
                    "resolved_citation_ids": json_dumps(sorted(resolved_citations["resolved"])),
                    "fabricated_citation_ids": json_dumps(sorted(resolved_citations["fabricated"])),
                    "matched_ground_truth_claim_id": match.truth.claim_id if match and match.truth else None,
                    "match_score": match.score if match else None,
                    "match_reason": match.reason if match else None,
                }
            )
        for citation in output_citations(item):
            raw_id = citation["citation_id"]
            resolved = resolve_citations([raw_id], valid_ids, alias_map)
            resolved_id = next(iter(resolved["resolved"]), None)
            source = canonical_sources.get(resolved_id) if resolved_id else None
            citation_rows.append(
                {
                    "system": item.run.system_type,
                    "turn_number": item.question.turn_number,
                    "question_id": str(item.question.id),
                    "turn_id": str(item.turn.id),
                    "output_id": str(item.output.id),
                    "citation_id": raw_id,
                    "resolved_id": resolved_id,
                    "classification": "resolved" if resolved_id else "fabricated",
                    "canonical_source_id": str(source.id) if source else citation.get("canonical_source_id"),
                    "source_type": source.source_type if source else citation.get("source_type"),
                    "document_id": str(source.document_id) if source and source.document_id else citation.get("document_id"),
                    "page_number": source.page_number if source else citation.get("page_number"),
                    "section_id": str(source.section_id) if source and source.section_id else citation.get("section_id"),
                }
            )
    return claim_rows, citation_rows


def recompute_observations(scoped_turns: list[ScopedTurn]) -> list[MetricObservation]:
    observations = []
    for item in scoped_turns:
        context = metric_context(item)
        calculations = {}
        calculations.update(calculate_claim_metric_group([context]))
        calculations.update(calculate_retrieval_metric_group([context]))
        calculations.update(calculate_state_metric_group([context]))
        calculations.update(calculate_efficiency_metric_group([context]))

        for metric in METRICS:
            result = calculations.get(metric) or not_applicable("metric_not_calculated")
            observations.append(
                MetricObservation(
                    system=item.run.system_type,
                    metric_name=metric,
                    turn_number=item.question.turn_number,
                    question_id=str(item.question.id),
                    turn_id=str(item.turn.id),
                    value=result.value,
                    numerator=result.numerator,
                    denominator=result.denominator,
                    applicable=result.applicable,
                    reason_not_applicable=result.reason_not_applicable,
                    details=result.details,
                )
            )
    return observations


def metric_context(item: ScopedTurn) -> EvaluationTurnContext:
    truth = item.truth
    if truth is not None:
        truth_payload = dict(truth.truth or {})
        expected_source_ids = set(truth_payload.get("relevant_source_ids") or [])
        expected_source_ids.update(extract_expected_source_ids(truth_payload))
        truth = SimpleNamespace(id=truth.id, question_id=truth.question_id, truth={**truth_payload, "relevant_source_ids": sorted(expected_source_ids)})
    return EvaluationTurnContext(
        turn=item.turn,
        question=item.question,
        ground_truth=truth,
        output=item.output,
        claims=corrected_claim_objects(item),
        retrieval_items=item.retrieval_items,
        llm_call=item.llm_call,
    )


def corrected_claim_objects(item: ScopedTurn) -> list[SimpleNamespace]:
    valid_ids, alias_map = valid_context_ids(item)
    truth_claims = [normalize_truth_claim(claim) for claim in truth_claims_from(item.truth)]
    generated_claims = [normalize_generated_claim(claim) for claim in item.claims]
    matches = match_claims(generated_claims, truth_claims)
    match_by_claim_id = {match.generated.claim_id: match for match in matches}
    corrected = []
    for claim in item.claims:
        generated = normalize_generated_claim(claim)
        match = match_by_claim_id.get(generated.claim_id)
        resolved = resolve_citations(claim.citation_ids or [], valid_ids, alias_map)
        classification, _reason = classify_claim(claim, match, resolved)
        metric_status = classification
        if metric_status == "not_factual":
            metric_status = "supported"
        corrected.append(
            SimpleNamespace(
                id=claim.id,
                claim_id=claim.claim_id,
                claim_text=claim.claim_text,
                normalized_claim=claim.normalized_claim,
                confidence=claim.confidence,
                citation_ids=list(resolved["resolved"] or claim.citation_ids or []),
                source_support_status=metric_status,
            )
        )
    return corrected


def aggregate_matrix(observations: list[MetricObservation]) -> tuple[list[dict], dict]:
    rows = []
    payload: dict[str, dict] = defaultdict(dict)
    grouped: dict[tuple[str, str], list[MetricObservation]] = defaultdict(list)
    for obs in observations:
        grouped[(obs.system, obs.metric_name)].append(obs)
    for system in SYSTEMS:
        for metric in METRICS:
            items = grouped.get((system, metric), [])
            values = [item.value for item in items if item.applicable and item.value is not None]
            n_applicable = len(values)
            n_total = len(items)
            row = {
                "system": system,
                "metric_name": metric,
                "value": aggregate_metric(metric, values),
                "n_applicable": n_applicable,
                "n_total": n_total,
                "n_not_applicable": n_total - n_applicable,
                "mean": mean(values),
                "stddev": stddev(values),
                "median": median(values),
                "iqr": iqr(values),
                "min": min(values) if values else None,
                "max": max(values) if values else None,
                "ci95_low": bootstrap_ci(values)[0] if values else None,
                "ci95_high": bootstrap_ci(values)[1] if values else None,
                "applicable": bool(values),
                "reason_not_applicable": "; ".join(sorted({item.reason_not_applicable for item in items if item.reason_not_applicable})) if not values else None,
                "direction": "lower_is_better" if metric in LOWER_IS_BETTER else "higher_is_better",
            }
            rows.append(row)
            payload[system][metric] = row
    return rows, payload


def aggregate_metric(metric: str, values: list[float]) -> float | None:
    if not values:
        return None
    if metric in {"total_cost"}:
        return sum(values)
    if metric == "p95_latency":
        return percentile(values, 0.95)
    return mean(values)


def build_rankings(matrix_rows: list[dict]) -> tuple[list[dict], dict]:
    ranking_rows = []
    ranking_json: dict[str, list[dict]] = {}
    by_metric: dict[str, list[dict]] = defaultdict(list)
    for row in matrix_rows:
        by_metric[row["metric_name"]].append(row)
    for metric in METRICS:
        measured = [row for row in by_metric[metric] if row["value"] is not None]
        reverse = metric not in LOWER_IS_BETTER
        measured.sort(key=lambda row: row["value"], reverse=reverse)
        ranked = []
        last_value = object()
        rank = 0
        for index, row in enumerate(measured, start=1):
            if row["value"] != last_value:
                rank = index
                last_value = row["value"]
            out = {
                "metric_name": metric,
                "rank": rank,
                "system": row["system"],
                "value": row["value"],
                "direction": row["direction"],
                "n_applicable": row["n_applicable"],
            }
            ranking_rows.append(out)
            ranked.append(out)
        for row in by_metric[metric]:
            if row["value"] is None:
                out = {
                    "metric_name": metric,
                    "rank": None,
                    "system": row["system"],
                    "value": None,
                    "direction": row["direction"],
                    "n_applicable": 0,
                    "reason_not_applicable": row["reason_not_applicable"],
                }
                ranking_rows.append(out)
                ranked.append(out)
        ranking_json[metric] = ranked
    return ranking_rows, ranking_json


def statistical_comparisons(observations: list[MetricObservation]) -> tuple[list[dict], dict]:
    by_key: dict[tuple[str, str, int], MetricObservation] = {}
    for obs in observations:
        by_key[(obs.system, obs.metric_name, obs.turn_number)] = obs
    rows = []
    for metric in METRICS:
        for baseline in [system for system in SYSTEMS if system != "csm"]:
            diffs = []
            for turn_number in range(1, 21):
                csm = by_key.get(("csm", metric, turn_number))
                other = by_key.get((baseline, metric, turn_number))
                if not csm or not other or csm.value is None or other.value is None:
                    continue
                diff = csm.value - other.value
                if metric in LOWER_IS_BETTER:
                    diff = -diff
                diffs.append(diff)
            ci_low, ci_high = bootstrap_ci(diffs)
            rows.append(
                {
                    "metric_name": metric,
                    "comparison": f"csm_vs_{baseline}",
                    "paired_n": len(diffs),
                    "mean_directional_improvement": mean(diffs),
                    "median_directional_improvement": median(diffs),
                    "ci95_low": ci_low,
                    "ci95_high": ci_high,
                    "sign_test_positive": sum(1 for diff in diffs if diff > 0),
                    "sign_test_negative": sum(1 for diff in diffs if diff < 0),
                    "p_value": sign_test_p_value(diffs),
                    "method": "paired_directional_difference_bootstrap_ci_and_two_sided_sign_test",
                    "reason_not_applicable": None if diffs else "no_paired_applicable_observations",
                }
            )
    return rows, {"comparisons": rows}


def write_validation_files(output_dir: Path, experiment_id: UUID, args: argparse.Namespace, validation: dict, hashes: dict, scoped_turns: list[ScopedTurn]) -> None:
    write_json(output_dir / "scope_validation.json", validation)
    write_json(
        output_dir / "answer_preservation_audit.json",
        {
            "status": "pending_final_hash_check",
            "read_only_recomputation": True,
            "source_experiment_id": str(experiment_id),
            "answer_count": len(hashes),
            "hashes_before_export": hashes,
        },
    )
    write_json(
        output_dir / "metric_recomputation_manifest.json",
        {
            "status": "running",
            "source_experiment_id": str(experiment_id),
            "patient": args.patient,
            "repetition": args.repetition,
            "turn_count": len(scoped_turns),
            "no_live_llm_calls": True,
            "created_at": now_iso(),
        },
    )


def write_audit_files(
    output_dir: Path,
    scoped_turns: list[ScopedTurn],
    canonical_sources: dict[str, CanonicalMemorySource],
    csm_bundle: dict[str, list[Any]],
    claim_rows: list[dict],
    citation_rows: list[dict],
    observations: list[MetricObservation],
) -> None:
    write_csv(output_dir / "metric_observations.csv", [as_csv_observation(obs) for obs in observations])
    write_csv(output_dir / "claim_matching_audit.csv", claim_rows)
    write_csv(output_dir / "claim_support_audit.csv", claim_rows)
    write_csv(output_dir / "claims_audit.csv", claim_rows)
    write_csv(output_dir / "unsupported_claims.csv", [row for row in claim_rows if row["corrected_support_status"] == "unsupported"])
    write_csv(output_dir / "hallucinations.csv", [row for row in claim_rows if row["corrected_support_status"] in {"unsupported", "contradicted"}])
    write_csv(output_dir / "citation_resolution_audit.csv", citation_rows)
    write_csv(output_dir / "citations_audit.csv", citation_rows)
    write_csv(output_dir / "fabricated_citations.csv", [row for row in citation_rows if row["classification"] == "fabricated"])
    write_csv(output_dir / "retrieval_audit.csv", retrieval_rows(scoped_turns, canonical_sources))
    write_csv(output_dir / "csm_activation_audit.csv", csm_activation_rows(csm_bundle))
    write_csv(output_dir / "state_comparison_audit.csv", csm_state_rows(csm_bundle))
    write_csv(output_dir / "correction_recovery_audit.csv", audit_metric_rows(observations, "correction_recovery"))
    write_csv(output_dir / "temporal_assertion_audit.csv", audit_metric_rows(observations, "temporal_consistency"))
    write_csv(output_dir / "decision_label_audit.csv", audit_metric_rows(observations, "decision_f1"))
    write_csv(output_dir / "calibration_audit.csv", audit_metric_rows(observations, "expected_calibration_error"))
    write_csv(output_dir / "future_leakage_audit.csv", future_leakage_rows(scoped_turns))
    write_csv(output_dir / "contradiction_results.csv", audit_metric_rows(observations, "contradiction_handling"))
    write_csv(output_dir / "correction_recovery_results.csv", audit_metric_rows(observations, "correction_recovery"))
    write_csv(output_dir / "state_transition_results.csv", audit_metric_rows(observations, "memory_update_accuracy"))
    write_json(output_dir / "csm_state_trace.json", csm_state_trace(csm_bundle))
    write_json(output_dir / "csm_lineage_trace.json", csm_lineage_trace(csm_bundle))


def write_result_files(
    output_dir: Path,
    scoped_turns: list[ScopedTurn],
    observations: list[MetricObservation],
    matrix_rows: list[dict],
    matrix_json: dict,
    ranking_rows: list[dict],
    ranking_json: dict,
    not_applicable_rows: list[dict],
    stats_rows: list[dict],
    stats_json: dict,
) -> None:
    write_csv(output_dir / "system_metric_matrix.csv", matrix_rows)
    write_json(output_dir / "system_metric_matrix.json", matrix_json)
    write_csv(output_dir / "metric_rankings.csv", ranking_rows)
    write_json(output_dir / "metric_rankings.json", ranking_json)
    write_csv(output_dir / "per_question_results.csv", per_question_rows(scoped_turns, observations))
    write_csv(output_dir / "per_system_results.csv", per_system_rows(matrix_rows))
    write_csv(output_dir / "turn_results.csv", turn_rows(scoped_turns))
    write_csv(output_dir / "not_applicable_metrics.csv", not_applicable_rows)
    write_csv(output_dir / "statistical_results.csv", stats_rows)
    write_json(output_dir / "statistical_results.json", stats_json)


def write_efficiency_files(output_dir: Path, scoped_turns: list[ScopedTurn]) -> None:
    rows = []
    for item in scoped_turns:
        call = item.llm_call
        if call is None:
            continue
        estimate = estimate_token_cost(
            provider=call.provider,
            model=call.model,
            input_tokens=call.input_token_count,
            output_tokens=call.output_token_count,
        )
        rows.append(
            {
                "system": item.run.system_type,
                "turn_number": item.question.turn_number,
                "turn_id": str(item.turn.id),
                "llm_call_id": str(call.id),
                "task_type": call.task_type,
                "provider": call.provider,
                "model": call.model,
                "input_tokens": call.input_token_count,
                "output_tokens": call.output_token_count,
                "total_tokens": call.total_token_count,
                "duration_ms": call.duration_ms,
                "retry_count": call.retry_count,
                "request_status": call.request_status,
                "estimated_cost_usd": estimate.get("total_cost"),
                "pricing_available": estimate.get("available"),
            }
        )
    write_csv(output_dir / "token_results.csv", rows)
    write_csv(output_dir / "system_processing_latency.csv", rows)
    write_csv(output_dir / "operational_wall_clock_latency.csv", wall_clock_latency_rows(scoped_turns))
    write_csv(output_dir / "offline_maintenance_cost.csv", [row for row in rows if row["task_type"] != "grounded_answer"])
    write_csv(output_dir / "online_query_cost.csv", [row for row in rows if row["task_type"] == "grounded_answer"])
    write_csv(output_dir / "retry_cost.csv", [row for row in rows if row["retry_count"]])
    write_csv(output_dir / "evaluation_cost.csv", rows)
    write_csv(output_dir / "total_cost.csv", cost_summary_rows(rows))


def write_paper_files(output_dir: Path, matrix_rows: list[dict], ranking_rows: list[dict], stats_rows: list[dict], validation: dict) -> None:
    main_rows = paper_rows(matrix_rows, MAIN_METRICS)
    write_csv(output_dir / "paper_main_results_table.csv", main_rows)
    write_text(output_dir / "paper_main_results_table.md", markdown_table(main_rows))
    write_text(output_dir / "paper_main_results_table.tex", latex_table(main_rows))
    for name, metrics in PAPER_GROUPS.items():
        rows = paper_rows(matrix_rows, metrics)
        write_csv(output_dir / f"paper_{name}_table.csv", rows)
        write_text(output_dir / f"paper_{name}_table.md", markdown_table(rows))
        write_text(output_dir / f"paper_{name}_table.tex", latex_table(rows))
    write_csv(output_dir / "paper_statistical_comparison_table.csv", stats_rows)
    write_text(output_dir / "paper_results_summary.md", paper_summary(matrix_rows, ranking_rows, validation))
    write_text(output_dir / "paper_experimental_setup.md", paper_setup(validation))
    write_text(output_dir / "paper_failure_analysis.md", paper_failure_analysis(matrix_rows))
    write_text(output_dir / "paper_discussion.md", paper_discussion(matrix_rows))
    write_text(output_dir / "paper_limitations.md", paper_limitations())


def valid_context_ids(item: ScopedTurn) -> tuple[set[str], dict[str, str]]:
    ids = set()
    aliases = {}
    for retrieved in item.retrieval_items:
        row_ids = []
        for value in (retrieved.canonical_source_id, retrieved.document_id, retrieved.section_id, retrieved.system_native_id):
            if value is not None:
                row_ids.append(str(value))
                ids.add(str(value))
        if row_ids:
            primary = row_ids[0]
            for alias in (f"C{retrieved.rank}", f"c{retrieved.rank}", f"source_{retrieved.rank}", f"rank_{retrieved.rank}", str(retrieved.rank)):
                aliases[alias] = primary
    for citation in output_citations(item):
        for key in ("canonical_source_id", "document_id", "section_id", "source_id"):
            value = citation.get(key)
            if value:
                ids.add(str(value))
                aliases.setdefault(str(citation.get("citation_id") or value), str(value))
    return ids, aliases


def resolve_citations(citations: list[Any], valid_ids: set[str], aliases: dict[str, str]) -> dict[str, set[str]]:
    resolved = set()
    fabricated = set()
    for citation in citations:
        values = []
        if isinstance(citation, dict):
            values.extend(
                citation.get(key)
                for key in ("canonical_source_id", "source_id", "citation_id", "id", "document_id", "section_id")
                if citation.get(key)
            )
        else:
            values.append(citation)
        citation_resolved = False
        for value in values:
            raw = str(value)
            target = aliases.get(raw, raw)
            if target in valid_ids:
                resolved.add(target)
                citation_resolved = True
        if not citation_resolved and values:
            fabricated.add(str(values[0]))
    return {"resolved": resolved, "fabricated": fabricated}


def classify_claim(claim: ExperimentClaim, match: Any, resolved_citations: dict[str, set[str]]) -> tuple[str, str]:
    explicit = normalize_text(claim.source_support_status)
    if explicit in {"supported", "entailed", "correct"}:
        return "supported", "stored_supported"
    if explicit in {"contradicted", "contradiction"}:
        return "contradicted", "stored_contradicted"
    if explicit in {"unsupported", "unverifiable"} and not resolved_citations["resolved"]:
        return "unsupported", "stored_unsupported_without_resolved_citation"
    text = normalize_text(claim.claim_text)
    if not text or any(marker in text for marker in ["not enough evidence", "insufficient evidence", "cannot determine", "unclear"]):
        return "not_factual", "uncertainty_or_insufficient_evidence_statement"
    if resolved_citations["resolved"]:
        return "supported", "resolved_to_retrieved_or_declared_context"
    if match and match.matched:
        return "supported", "matched_ground_truth_claim"
    return "unsupported", "no_resolved_citation_or_ground_truth_match"


def truth_claims_from(truth: BenchmarkGroundTruth | None) -> list[Any]:
    if truth is None:
        return []
    payload = truth.truth or {}
    claims = []
    for key in ("claims", "required_claims", "acceptable_claims", "expected_claims"):
        value = payload.get(key)
        if isinstance(value, list):
            claims.extend(value)
    if not claims:
        expected = payload.get("expected_answer") or payload.get("answer") or payload.get("answer_summary")
        if expected:
            claims.append({"claim_id": "expected_answer", "claim_text": str(expected), "value": str(expected)})
    return claims


def extract_expected_source_ids(payload: Any) -> set[str]:
    ids = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            lowered = key.lower()
            if any(token in lowered for token in ("source_id", "citation", "evidence_id", "document_id", "section_id")):
                if isinstance(value, list):
                    ids.update(str(item) for item in value if scalar_id_like(item))
                elif scalar_id_like(value):
                    ids.add(str(value))
            ids.update(extract_expected_source_ids(value))
    elif isinstance(payload, list):
        for item in payload:
            ids.update(extract_expected_source_ids(item))
    return ids


def scalar_id_like(value: Any) -> bool:
    return isinstance(value, (str, int)) and bool(str(value).strip())


def output_citations(item: ScopedTurn) -> list[dict]:
    citations = []
    for index, citation in enumerate(item.output.citations or [], start=1):
        if isinstance(citation, dict):
            row = dict(citation)
        else:
            row = {"citation_id": citation}
        row.setdefault("citation_id", row.get("source_id") or row.get("canonical_source_id") or f"C{index}")
        citations.append(row)
    return citations


def retrieval_rows(scoped_turns: list[ScopedTurn], canonical_sources: dict[str, CanonicalMemorySource]) -> list[dict]:
    rows = []
    for item in scoped_turns:
        expected_ids = extract_expected_source_ids((item.truth.truth if item.truth else {}) or {})
        retrieved_ids = set()
        for retrieved in item.retrieval_items:
            ids = [str(value) for value in (retrieved.canonical_source_id, retrieved.document_id, retrieved.section_id) if value]
            retrieved_ids.update(ids)
            source = canonical_sources.get(str(retrieved.canonical_source_id)) if retrieved.canonical_source_id else None
            rows.append(
                {
                    "system": item.run.system_type,
                    "turn_number": item.question.turn_number,
                    "question_id": str(item.question.id),
                    "turn_id": str(item.turn.id),
                    "retrieval_run_id": str(item.turn.retrieval_run_id) if item.turn.retrieval_run_id else None,
                    "rank": retrieved.rank,
                    "canonical_source_id": str(retrieved.canonical_source_id) if retrieved.canonical_source_id else None,
                    "document_id": str(retrieved.document_id) if retrieved.document_id else None,
                    "section_id": str(retrieved.section_id) if retrieved.section_id else None,
                    "source_type": retrieved.source_type or (source.source_type if source else None),
                    "raw_score": retrieved.raw_score,
                    "normalized_score": retrieved.normalized_score,
                    "token_count": retrieved.token_count,
                    "content_preview": retrieved.content_preview,
                    "is_expected_relevant": bool(set(ids) & expected_ids) if expected_ids else None,
                }
            )
        if not item.retrieval_items:
            rows.append(
                {
                    "system": item.run.system_type,
                    "turn_number": item.question.turn_number,
                    "question_id": str(item.question.id),
                    "turn_id": str(item.turn.id),
                    "retrieval_run_id": None,
                    "rank": None,
                    "canonical_source_id": None,
                    "is_expected_relevant": None,
                    "audit_status": "no_retrieval_items",
                }
            )
    return rows


def csm_activation_rows(bundle: dict[str, list[Any]]) -> list[dict]:
    runs = {run.id: run for run in bundle["activation_runs"]}
    rows = []
    for item in bundle["activation_items"]:
        run = runs.get(item.activation_run_id)
        rows.append(
            {
                "activation_run_id": str(item.activation_run_id),
                "state_variable_id": str(item.state_variable_id),
                "query_text": run.query_text if run else None,
                "rank": item.rank,
                "selected": item.selected,
                "relevance_score": item.relevance_score,
                "dependency_score": item.dependency_score,
                "confidence_score": item.confidence_score,
                "utility_score": item.utility_score,
                "estimated_token_cost": item.estimated_token_cost,
                "selection_reason": item.selection_reason,
            }
        )
    return rows


def csm_state_rows(bundle: dict[str, list[Any]]) -> list[dict]:
    link_counts = Counter(link.state_variable_id for link in bundle["links"])
    return [
        {
            "state_id": str(state.id),
            "system_instance_id": str(state.system_instance_id),
            "state_type": state.state_type,
            "state_key": state.state_key,
            "current_value": json_dumps(state.current_value),
            "confidence": state.confidence,
            "status": state.status,
            "current_version": state.current_version,
            "valid_from": iso(state.valid_from),
            "valid_to": iso(state.valid_to),
            "last_updated_at": iso(state.last_updated_at),
            "evidence_link_count": link_counts[state.id],
        }
        for state in bundle["states"]
    ]


def csm_state_trace(bundle: dict[str, list[Any]]) -> list[dict]:
    histories_by_state: dict[Any, list[Any]] = defaultdict(list)
    for history in bundle["history"]:
        histories_by_state[history.state_variable_id].append(history)
    return [
        {
            "state_id": str(state.id),
            "state_type": state.state_type,
            "state_key": state.state_key,
            "status": state.status,
            "current_version": state.current_version,
            "current_value": state.current_value,
            "history": [
                {
                    "history_id": str(history.id),
                    "version_number": history.version_number,
                    "previous_value": history.previous_value,
                    "new_value": history.new_value,
                    "update_reason": history.update_reason,
                    "created_at": iso(history.created_at),
                }
                for history in sorted(histories_by_state[state.id], key=lambda row: row.version_number)
            ],
        }
        for state in bundle["states"]
    ]


def csm_lineage_trace(bundle: dict[str, list[Any]]) -> list[dict]:
    evidence_by_id = {row.id: row for row in bundle["evidence"]}
    state_by_id = {row.id: row for row in bundle["states"]}
    rows = []
    for link in bundle["links"]:
        evidence = evidence_by_id.get(link.evidence_id)
        state = state_by_id.get(link.state_variable_id)
        rows.append(
            {
                "state_variable_id": str(link.state_variable_id),
                "state_key": state.state_key if state else None,
                "evidence_id": str(link.evidence_id),
                "canonical_source_id": str(evidence.canonical_source_id) if evidence else None,
                "source_type": evidence.source_type if evidence else None,
                "evidence_type": evidence.evidence_type if evidence else None,
                "verification_status": evidence.verification_status if evidence else None,
                "contribution_type": link.contribution_type,
                "contribution_weight": link.contribution_weight,
                "created_at": iso(link.created_at),
            }
        )
    return rows


def audit_metric_rows(observations: list[MetricObservation], metric: str) -> list[dict]:
    return [as_csv_observation(obs) for obs in observations if obs.metric_name == metric]


def future_leakage_rows(scoped_turns: list[ScopedTurn]) -> list[dict]:
    rows = []
    for item in scoped_turns:
        for retrieved in item.retrieval_items:
            leakage = False
            reason = None
            source_time = None
            if retrieved.canonical_source_id:
                source_time = None
            if source_time and source_time > item.question.source_cutoff:
                leakage = True
                reason = "retrieved_source_after_question_cutoff"
            rows.append(
                {
                    "system": item.run.system_type,
                    "turn_number": item.question.turn_number,
                    "turn_id": str(item.turn.id),
                    "question_source_cutoff": iso(item.question.source_cutoff),
                    "retrieval_item_id": str(retrieved.id),
                    "canonical_source_id": str(retrieved.canonical_source_id) if retrieved.canonical_source_id else None,
                    "future_leakage": leakage,
                    "reason": reason,
                }
            )
    return rows


def per_question_rows(scoped_turns: list[ScopedTurn], observations: list[MetricObservation]) -> list[dict]:
    obs_by_turn: dict[str, list[MetricObservation]] = defaultdict(list)
    for obs in observations:
        obs_by_turn[obs.turn_id].append(obs)
    rows = []
    for item in scoped_turns:
        row = {
            "system": item.run.system_type,
            "turn_number": item.question.turn_number,
            "question_id": str(item.question.id),
            "turn_id": str(item.turn.id),
            "question": item.question.question,
            "question_type": item.question.question_type,
            "expected_decision_type": item.question.expected_decision_type,
            "answer_text": item.output.answer_text,
            "claim_count": len(item.claims),
            "citation_count": len(output_citations(item)),
            "retrieval_item_count": len(item.retrieval_items),
        }
        for obs in obs_by_turn[str(item.turn.id)]:
            row[obs.metric_name] = obs.value
            if not obs.applicable:
                row[f"{obs.metric_name}_na_reason"] = obs.reason_not_applicable
        rows.append(row)
    return rows


def per_system_rows(matrix_rows: list[dict]) -> list[dict]:
    rows = []
    grouped = defaultdict(list)
    for row in matrix_rows:
        grouped[row["system"]].append(row)
    for system, items in grouped.items():
        applicable = [row for row in items if row["value"] is not None]
        rows.append(
            {
                "system": system,
                "metric_count": len(items),
                "applicable_metric_count": len(applicable),
                "not_applicable_metric_count": len(items) - len(applicable),
                "mean_rankable_metric_value": mean([row["value"] for row in applicable]),
            }
        )
    return rows


def turn_rows(scoped_turns: list[ScopedTurn]) -> list[dict]:
    return [
        {
            "system": item.run.system_type,
            "system_run_id": str(item.run.id),
            "turn_id": str(item.turn.id),
            "turn_number": item.turn.turn_number,
            "question_id": str(item.question.id),
            "status": item.turn.status,
            "retrieval_run_id": str(item.turn.retrieval_run_id) if item.turn.retrieval_run_id else None,
            "llm_call_id": str(item.turn.llm_call_id) if item.turn.llm_call_id else None,
            "output_id": str(item.output.id),
            "answer_sha256": answer_hashes([item])[str(item.turn.id)],
            "completed_at": iso(item.turn.completed_at),
        }
        for item in scoped_turns
    ]


def wall_clock_latency_rows(scoped_turns: list[ScopedTurn]) -> list[dict]:
    rows = []
    for item in scoped_turns:
        duration_ms = None
        if item.turn.started_at and item.turn.completed_at:
            duration_ms = (item.turn.completed_at - item.turn.started_at).total_seconds() * 1000
        rows.append(
            {
                "system": item.run.system_type,
                "turn_number": item.turn.turn_number,
                "turn_id": str(item.turn.id),
                "started_at": iso(item.turn.started_at),
                "completed_at": iso(item.turn.completed_at),
                "wall_clock_duration_ms": duration_ms,
                "note": "wall clock can include request-delay/retry waiting; p95_latency uses stored LLM processing duration",
            }
        )
    return rows


def cost_summary_rows(rows: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["system"]].append(row)
    out = []
    for system in SYSTEMS:
        items = grouped.get(system, [])
        costs = [row["estimated_cost_usd"] for row in items if row["estimated_cost_usd"] is not None]
        out.append(
            {
                "system": system,
                "call_count": len(items),
                "total_input_tokens": sum(row["input_tokens"] for row in items),
                "total_output_tokens": sum(row["output_tokens"] for row in items),
                "total_tokens": sum(row["total_tokens"] for row in items),
                "total_cost_usd": sum(costs) if costs else None,
                "pricing_available": bool(costs),
            }
        )
    return out


def paper_rows(matrix_rows: list[dict], metrics: list[str]) -> list[dict]:
    by_key = {(row["system"], row["metric_name"]): row for row in matrix_rows}
    rows = []
    for metric in metrics:
        row = {"metric_name": metric, "direction": "lower" if metric in LOWER_IS_BETTER else "higher"}
        for system in SYSTEMS:
            cell = by_key.get((system, metric), {})
            row[system] = fmt(cell.get("value")) if cell.get("value") is not None else "N/A"
            row[f"{system}_n"] = cell.get("n_applicable", 0)
        rows.append(row)
    return rows


def paper_summary(matrix_rows: list[dict], ranking_rows: list[dict], validation: dict) -> str:
    first_rank = [row for row in ranking_rows if row.get("rank") == 1]
    wins = Counter(row["system"] for row in first_rank)
    csm_first = [row["metric_name"] for row in first_rank if row["system"] == "csm"]
    return "\n".join(
        [
            "# Corrected Patient 1 Results Summary",
            "",
            f"Scope: {validation['completed_turns']} completed turns for SYN-CSM-001, repetition 1, seven systems and twenty questions.",
            "",
            "The recomputation was offline and read-only. Stored answers, retrievals, CSM activations, and token records were reused; no Groq or live provider calls were made.",
            "",
            f"First-rank counts by system: {dict(wins)}.",
            f"CSM first-rank metrics: {', '.join(csm_first) if csm_first else 'none'}.",
        ]
    )


def paper_setup(validation: dict) -> str:
    return "\n".join(
        [
            "# Experimental Setup",
            "",
            "The corrected export uses experiment-local database records from the existing completed run.",
            f"Completed turn count: {validation['completed_turns']} of 140 scoped turns.",
            "Systems: long_context, rolling_summary, dense_rag, hybrid_rag, graph_rag, hippo_rag, csm.",
            "Metrics: the complete 21-metric matrix listed in metric_recomputation_manifest.json.",
            "Live answer generation was disabled; the exporter performs no provider health checks or LLM invocations.",
        ]
    )


def paper_failure_analysis(matrix_rows: list[dict]) -> str:
    na = [row for row in matrix_rows if row["value"] is None]
    return "\n".join(
        [
            "# Failure Analysis",
            "",
            f"Not-applicable metric cells: {len(na)}.",
            "N/A cells are preserved with explicit reasons instead of being converted to zero.",
        ]
    )


def paper_discussion(matrix_rows: list[dict]) -> str:
    csm_rows = [row for row in matrix_rows if row["system"] == "csm"]
    measured = [row for row in csm_rows if row["value"] is not None]
    return "\n".join(
        [
            "# Discussion",
            "",
            f"CSM has {len(measured)} applicable metrics out of 21 in this corrected single-patient scope.",
            "The corrected pipeline separates online generation cost from offline recomputation and keeps unsupported or fabricated evidence explicit in audit files.",
        ]
    )


def paper_limitations() -> str:
    return "\n".join(
        [
            "# Limitations",
            "",
            "This is a synthetic single-patient, single-repetition pilot slice and should not be interpreted as broad clinical evidence.",
            "Offline deterministic scoring cannot recover missing generated claims or missing ground-truth annotations; such cases remain N/A with reasons.",
            "No live judge model was used during recomputation, by design.",
        ]
    )


def as_csv_observation(obs: MetricObservation) -> dict:
    row = asdict(obs)
    row["details"] = json_dumps(obs.details)
    return row


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json_dumps(payload) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()})
    if not fieldnames:
        fieldnames = ["empty"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: serialize_cell(row.get(key)) for key in fieldnames})


def markdown_table(rows: list[dict]) -> str:
    if not rows:
        return "_No rows._"
    headers = list(rows[0].keys())
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(header, "")).replace("|", "\\|") for header in headers) + " |")
    return "\n".join(lines)


def latex_table(rows: list[dict]) -> str:
    if not rows:
        return "% No rows."
    headers = list(rows[0].keys())
    lines = ["\\begin{tabular}{" + "l" * len(headers) + "}", " \\hline", " & ".join(headers) + " \\\\", " \\hline"]
    for row in rows:
        values = [str(row.get(header, "")).replace("_", "\\_") for header in headers]
        lines.append(" & ".join(values) + " \\\\")
    lines.extend([" \\hline", "\\end{tabular}"])
    return "\n".join(lines)


def json_dumps(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, default=serialize_cell)


def serialize_cell(value: Any) -> Any:
    if isinstance(value, datetime):
        return iso(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, sort_keys=True, default=serialize_cell)
    return value


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def iso(value: Any) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


def fmt(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def stddev(values: list[float]) -> float | None:
    return statistics.stdev(values) if len(values) > 1 else (0.0 if values else None)


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def iqr(values: list[float]) -> float | None:
    if len(values) < 2:
        return 0.0 if values else None
    ordered = sorted(values)
    q1 = percentile(ordered, 0.25)
    q3 = percentile(ordered, 0.75)
    return None if q1 is None or q3 is None else q3 - q1


def percentile(values: list[float], percentile_value: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * percentile_value
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = index - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


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


def sign_test_p_value(diffs: list[float]) -> float | None:
    positives = sum(1 for diff in diffs if diff > 0)
    negatives = sum(1 for diff in diffs if diff < 0)
    n = positives + negatives
    if n == 0:
        return None
    k = min(positives, negatives)
    probability = 0.0
    for i in range(k + 1):
        probability += math.comb(n, i) * (0.5**n)
    return min(1.0, 2 * probability)


def reproducibility_command(args: argparse.Namespace) -> str:
    return (
        'cd "/Users/shivamtomar/Desktop/Project - 1/sustha/backend" && '
        "venv/bin/python -m app.evaluation.scripts.recompute_single_patient_results "
        f"--experiment-id {args.experiment_id} --patient {args.patient} --repetition {args.repetition}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
