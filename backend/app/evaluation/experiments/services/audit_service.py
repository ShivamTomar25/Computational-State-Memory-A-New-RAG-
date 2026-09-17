from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.evaluation.claims.matching.matcher import match_claims
from app.evaluation.claims.normalization.normalizer import normalize_citation_ids, normalize_generated_claim, normalize_truth_claim
from app.evaluation.experiments.repositories import experiment_result_repository as result_repository
from app.evaluation.metrics.calculators.claim_metrics import get_expected_source_ids, get_valid_context_source_ids
from app.evaluation.metrics.calculators.context import EvaluationTurnContext


def list_claim_audit(db: Session, experiment_id: UUID) -> list[dict]:
    contexts = build_contexts(db, experiment_id)
    audit_rows = []

    for context in contexts:
        truth_claims = [normalize_truth_claim(item) for item in ((getattr(context.ground_truth, "truth", {}) or {}).get("claims") or [])]
        generated_claims = [normalize_generated_claim(claim) for claim in context.claims]
        matches = match_claims(generated_claims, truth_claims)

        for claim, match in zip(context.claims, matches):
            audit_rows.append(
                {
                    "turn_id": str(context.turn.id),
                    "question_id": str(context.question.id),
                    "output_id": str(context.output.id),
                    "experiment_claim_id": str(claim.id),
                    "claim_id": match.generated.claim_id,
                    "claim_text": match.generated.claim_text,
                    "citation_ids": list(match.generated.citation_ids),
                    "support_status": support_status(match),
                    "match_score": match.score,
                    "matched_ground_truth_claim_id": match.truth.claim_id if match.truth else None,
                }
            )

    return audit_rows


def list_hallucination_audit(db: Session, experiment_id: UUID) -> list[dict]:
    return [
        row
        for row in list_claim_audit(db, experiment_id)
        if row["support_status"] in {"unsupported", "contradicted"}
    ]


def list_citation_audit(db: Session, experiment_id: UUID) -> list[dict]:
    contexts = build_contexts(db, experiment_id)
    expected_ids = get_expected_source_ids(contexts)
    valid_ids = get_valid_context_source_ids(contexts) | expected_ids
    rows = []

    for context in contexts:
        citation_ids = set()

        if context.output is not None:
            citation_ids.update(normalize_citation_ids(getattr(context.output, "citations", None)))

        for claim in context.claims:
            citation_ids.update(normalize_citation_ids(getattr(claim, "citation_ids", None)))

        for citation_id in sorted(citation_ids):
            rows.append(
                {
                    "turn_id": str(context.turn.id),
                    "question_id": str(context.question.id),
                    "citation_id": citation_id,
                    "status": "valid" if citation_id in valid_ids else "fabricated_or_unresolved",
                    "expected": citation_id in expected_ids,
                    "available_in_supplied_context": citation_id in valid_ids,
                }
            )

    return rows


def build_contexts(db: Session, experiment_id: UUID) -> list[EvaluationTurnContext]:
    turn_rows = result_repository.list_turns_with_questions(db, experiment_id)
    outputs_by_turn = {output.turn_id: output for output in result_repository.list_outputs(db, experiment_id)}
    claims_by_output = {}

    for claim in result_repository.list_claims(db, experiment_id):
        claims_by_output.setdefault(claim.output_id, []).append(claim)

    truth_by_question = {truth.question_id: truth for truth in result_repository.list_ground_truth(db, experiment_id)}
    retrieval_items_by_turn = {}

    for turn_id, item in result_repository.list_retrieval_items(db, experiment_id):
        retrieval_items_by_turn.setdefault(turn_id, []).append(item)

    llm_calls_by_turn = {turn_id: call for turn_id, call in result_repository.list_llm_calls(db, experiment_id)}
    contexts = []

    for turn, question in turn_rows:
        output = outputs_by_turn.get(turn.id)

        if output is None:
            continue

        contexts.append(
            EvaluationTurnContext(
                turn=turn,
                question=question,
                ground_truth=truth_by_question.get(question.id),
                output=output,
                claims=claims_by_output.get(output.id, []),
                retrieval_items=retrieval_items_by_turn.get(turn.id, []),
                llm_call=llm_calls_by_turn.get(turn.id),
            )
        )

    return contexts


def support_status(match) -> str:
    explicit_status = match.generated.source_support_status

    if explicit_status in {"supported", "entailed", "correct"}:
        return "supported"

    if explicit_status in {"contradicted", "contradiction"}:
        return "contradicted"

    if explicit_status in {"unsupported", "unverifiable"}:
        return "unsupported"

    return "supported" if match.matched else "unsupported"
