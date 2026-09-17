from __future__ import annotations

from collections import Counter, defaultdict

from app.evaluation.metrics.cost.pricing import estimate_token_cost
from app.evaluation.offline_recomputation.claim_matcher import claim_text, expected_claims, match_generated_claims, semantic_score
from app.evaluation.offline_recomputation.claim_support_classifier import classify_claim
from app.evaluation.offline_recomputation.citation_resolver import resolve_turn_citations
from app.evaluation.offline_recomputation.correction_evaluator import correction_score
from app.evaluation.offline_recomputation.csm_lineage_resolver import csm_alias_map
from app.evaluation.offline_recomputation.decision_evaluator import decision_f1
from app.evaluation.offline_recomputation.scope_loader import OfflineScope, OfflineTurn
from app.evaluation.offline_recomputation.state_evaluator import csm_state_accuracy, memory_update_accuracy
from app.evaluation.offline_recomputation.temporal_evaluator import temporal_expected, temporal_score


CSM_SYSTEMS = {"csm", "csm_v3", "csm_v4"}


def build_all(scope: OfflineScope) -> dict[str, list[dict]]:
    csm_aliases = csm_alias_map(scope.csm)
    claim_matching_rows = []
    answer_f1_rows = []
    claim_support_rows = []
    citation_rows = []
    retrieval_rows = []
    observations = []

    for turn in scope.turns:
        citation_resolutions = resolve_turn_citations(turn, csm_aliases if is_csm_system(turn.system_run.system_type) else {})
        matches = match_generated_claims(turn.claims, turn.ground_truth)
        citation_by_raw = defaultdict(list)
        for row in citation_resolutions:
            citation_by_raw[row.raw_id].append(row)

        local_matching_rows = []
        local_support_rows = []
        for match in matches:
            claim = next((item for item in turn.claims if str(item.claim_id) == match.claim_id), None)
            citations = []
            if claim is not None:
                for citation in claim.citation_ids or []:
                    key = str(citation.get("citation_id") if isinstance(citation, dict) else citation)
                    citations.extend(citation_by_raw.get(key, []))
            status, reason = classify_claim(claim, match, citations) if claim is not None else ("not_factual", "missing_claim_object")
            matching_row = base(turn) | {
                "claim_id": match.claim_id,
                "claim_text": getattr(claim, "claim_text", None),
                "matched_ground_truth_claim": match.matched_truth_text,
                "correctness": match.correctness,
                "match_score": match.score,
                "claim_match_classification": claim_match_classification(claim, match, status),
                "calculation_reason": match.reason,
            }
            local_matching_rows.append(matching_row)
            local_support_rows.append(base(turn) | {
                "claim_id": match.claim_id,
                "claim_text": getattr(claim, "claim_text", None),
                "support_classification": status,
                "calculation_reason": reason,
            })

        matched_truth_ids = {row.matched_truth_id for row in matches if row.correctness and row.matched_truth_id}
        for expected in expected_claims(turn.ground_truth):
            if expected["id"] in matched_truth_ids:
                continue
            local_matching_rows.append(base(turn) | {
                "claim_id": f"FN:{expected['id']}",
                "claim_text": None,
                "matched_ground_truth_claim": expected["text"],
                "correctness": False,
                "match_score": 0.0,
                "claim_match_classification": "false_negative",
                "calculation_reason": "required_ground_truth_claim_not_generated",
            })

        answer_row = answer_f1_row(turn, local_matching_rows)
        answer_f1_rows.append(answer_row)
        claim_matching_rows.extend(local_matching_rows)
        claim_support_rows.extend(local_support_rows)

        for citation in citation_resolutions:
            citation_rows.append(base(turn) | {
                "citation_id": citation.raw_id,
                "resolved_id": citation.resolved_id,
                "resolution_status": citation_resolution_status(citation.classification),
                "citation_classification": citation.classification,
                "calculation_reason": citation.calculation_reason,
            })

        retrieval_rows.extend(retrieval_resolution_rows(turn, scope, csm_aliases))
        observations.extend(turn_metric_observations(turn, answer_row, local_support_rows, citation_resolutions, scope, csm_aliases))

    return {
        "metric_observations": observations,
        "claim_matching_audit": claim_matching_rows,
        "answer_f1_audit": answer_f1_rows,
        "claim_support_audit": claim_support_rows,
        "citation_resolution_audit": citation_rows,
        "retrieval_identifier_resolution_audit": retrieval_rows,
    }


def turn_metric_observations(turn: OfflineTurn, answer_row: dict, supports, citations, scope: OfflineScope, csm_aliases: dict[str, str]) -> list[dict]:
    rows = []
    support_counts = Counter(row["support_classification"] for row in supports)
    factual = sum(support_counts[key] for key in ("supported", "partially_supported", "unsupported", "contradicted"))
    supported = support_counts["supported"] + 0.5 * support_counts["partially_supported"]
    unsupported = support_counts["unsupported"]
    hallucinated = support_counts["unsupported"] + support_counts["contradicted"]
    valid_cites = [row for row in citations if row.classification.startswith("valid")]
    fabricated = [row for row in citations if row.classification == "fabricated"]

    rows.append(obs(turn, "answer_accuracy", answer_row["f1"], answer_row["applicable"], answer_row["reason_not_applicable"], answer_row["true_positive"], answer_row["true_positive"] + answer_row["false_positive"] + answer_row["false_negative"], "answer_f1_audit.csv", "per_question_claim_level_f1"))
    rows.append(obs(turn, "hallucination_rate", hallucinated / factual if factual else None, bool(factual), "no_factual_claims", hallucinated, factual, "claim_support_audit.csv", "unsupported_or_contradicted_factual_claims"))
    rows.append(obs(turn, "evidence_support_rate", supported / factual if factual else None, bool(factual), "no_factual_claims", supported, factual, "claim_support_audit.csv", "supported_factual_claims"))
    rows.append(obs(turn, "unsupported_claim_rate", unsupported / factual if factual else None, bool(factual), "no_factual_claims", unsupported, factual, "claim_support_audit.csv", "unsupported_factual_claims"))
    rows.append(obs(turn, "fabricated_citation_rate", len(fabricated) / len(citations) if citations else None, bool(citations), "no_generated_citations", len(fabricated), len(citations), "citation_resolution_audit.csv", "fabricated_citations_over_generated_citations"))
    rows.append(obs(turn, "faithfulness", supported / factual if factual else None, bool(factual), "no_factual_claims", supported, factual, "claim_support_audit.csv", "claim_level_context_support_classification"))
    rows.append(obs(turn, "groundedness", supported / factual if factual else None, bool(factual), "no_factual_claims", supported, factual, "claim_support_audit.csv", "supported_or_partially_supported_claims"))

    retrieval_expected = expected_source_ids(turn, scope)
    retrieved_ids = retrieved_source_ids(turn, csm_aliases)
    relevant = retrieved_ids & retrieval_expected
    rows.append(obs(turn, "retrieval_precision", len(relevant) / len(retrieved_ids) if retrieved_ids and retrieval_expected else None, bool(retrieved_ids and retrieval_expected), "missing_retrieved_or_expected_sources", len(relevant), len(retrieved_ids), "retrieval_audit.csv", "retrieved_relevant_sources_over_retrieved_sources"))
    rows.append(obs(turn, "retrieval_recall", len(relevant) / len(retrieval_expected) if retrieved_ids and retrieval_expected else None, bool(retrieved_ids and retrieval_expected), "missing_retrieved_or_expected_sources", len(relevant), len(retrieval_expected), "retrieval_audit.csv", "retrieved_relevant_sources_over_expected_sources"))
    rows.append(obs(turn, "lineage_citation_f1", citation_f1(valid_cites, retrieval_expected), bool(citations and retrieval_expected), "missing_citations_or_expected_sources", None, None, "citation_resolution_audit.csv", "citation_lineage_f1_against_expected_sources"))
    if is_csm_system(turn.system_run.system_type):
        rows.append(obs(turn, "activation_precision", len(relevant) / len(retrieved_ids) if retrieved_ids and retrieval_expected else None, bool(retrieved_ids and retrieval_expected), "missing_csm_activation_or_expected_sources", len(relevant), len(retrieved_ids), "csm_activation_audit.csv", "activated_state_canonical_evidence_precision"))
        rows.append(obs(turn, "activation_recall", len(relevant) / len(retrieval_expected) if retrieved_ids and retrieval_expected else None, bool(retrieved_ids and retrieval_expected), "missing_csm_activation_or_expected_sources", len(relevant), len(retrieval_expected), "csm_activation_audit.csv", "activated_state_canonical_evidence_recall"))
    else:
        rows.append(obs(turn, "activation_precision", None, False, "activation_metric_only_applicable_to_csm", None, None, "csm_activation_audit.csv", "non_csm_has_no_csm_activation"))
        rows.append(obs(turn, "activation_recall", None, False, "activation_metric_only_applicable_to_csm", None, None, "csm_activation_audit.csv", "non_csm_has_no_csm_activation"))

    temporal_value, temporal_reason = temporal_score(turn.output.answer_text or "", temporal_expected(turn.ground_truth, turn.question))
    rows.append(obs(turn, "temporal_consistency", temporal_value, temporal_value is not None, temporal_reason if temporal_value is None else None, None, None, "temporal_assertion_audit.csv", temporal_reason))
    decision_value, decision_reason, expected_labels, predicted_labels = decision_f1(turn.output.answer_text or "", turn.ground_truth, turn.question)
    rows.append(obs(turn, "decision_f1", decision_value, decision_value is not None, decision_reason if decision_value is None else None, None, None, "decision_label_audit.csv", f"{decision_reason}; expected={sorted(expected_labels)} predicted={sorted(predicted_labels)}"))
    correction_value, correction_reason = correction_score(turn.output.answer_text or "", turn.question, turn.ground_truth)
    rows.append(obs(turn, "correction_recovery", correction_value, correction_value is not None, correction_reason if correction_value is None else None, None, None, "correction_recovery_audit.csv", correction_reason))
    update_value, update_reason = memory_update_accuracy(turn.output.answer_text or "", turn.ground_truth)
    rows.append(obs(turn, "memory_update_accuracy", update_value, update_value is not None, update_reason if update_value is None else None, None, None, "state_comparison_audit.csv", update_reason))

    if is_csm_system(turn.system_run.system_type):
        state_value, state_reason, state_details = csm_state_accuracy(scope.csm, turn.ground_truth)
        rows.append(obs(turn, "state_accuracy", state_value, state_value is not None, state_reason if state_value is None else None, state_details.get("matched"), state_details.get("expected"), "state_comparison_audit.csv", state_reason))
        rows.append(obs(turn, "state_recovery_time", 1.0 if correction_value and correction_value > 0 else None, bool(correction_value), "no_recovered_correction_state", None, None, "correction_recovery_audit.csv", "first_turn_recovery_credit_when_corrected_state_available"))
    else:
        rows.append(obs(turn, "state_accuracy", None, False, "state_table_metric_only_applicable_to_csm", None, None, "state_comparison_audit.csv", "non_csm_system_has_no_state_table"))
        rows.append(obs(turn, "state_recovery_time", None, False, "state_recovery_time_only_applicable_to_csm", None, None, "correction_recovery_audit.csv", "non_csm_system_has_no_recovery_state"))

    confidence_values = [float(getattr(claim, "confidence", 0.0)) for claim in turn.claims if getattr(claim, "confidence", None) is not None]
    rows.append(obs(turn, "expected_calibration_error", calibration_error(confidence_values, supports), bool(confidence_values), "missing_generated_confidence", None, None, "calibration_audit.csv", "absolute_confidence_error_against_support_classification"))

    call = turn.llm_call
    if call is not None:
        cost = estimate_token_cost(provider=call.provider, model=call.model, input_tokens=call.input_token_count, output_tokens=call.output_token_count)
        rows.append(obs(turn, "tokens_per_query", call.total_token_count, True, None, call.total_token_count, 1, "token_results.csv", "stored_llm_call_total_tokens"))
        rows.append(obs(turn, "provider_generation_latency_ms", call.duration_ms, True, None, call.duration_ms, 1, "latency_definition_audit.csv", "stored_provider_generation_latency_ms_excludes_external_request_delay_column"))
        retrieval_duration = turn.retrieval_run.duration_ms if turn.retrieval_run else None
        rows.append(obs(turn, "retrieval_activation_latency_ms", retrieval_duration, retrieval_duration is not None, "missing_retrieval_run", retrieval_duration, 1, "latency_definition_audit.csv", "stored_retrieval_or_csm_activation_duration_ms"))
        rows.append(obs(turn, "processing_latency_ms", call.duration_ms, True, None, call.duration_ms, 1, "latency_definition_audit.csv", "primary_processing_latency_excludes_intentional_request_delay_and_quota_backoff"))
        operational = (call.duration_ms or 0) + (retrieval_duration or 0)
        rows.append(obs(turn, "operational_wall_clock_latency_ms", operational, True, None, operational, 1, "latency_definition_audit.csv", "retrieval_plus_provider_generation_latency_without_configured_request_delay"))
        rows.append(obs(turn, "p95_latency", call.duration_ms, True, None, call.duration_ms, 1, "latency_definition_audit.csv", "stored_llm_call_processing_duration_ms"))
        rows.append(obs(turn, "online_query_cost", cost.get("total_cost"), bool(cost.get("available")), "pricing_not_configured", cost.get("total_cost"), 1, "total_cost.csv", "answer_generation_provider_token_cost"))
        rows.append(obs(turn, "offline_csm_update_cost", 0.0 if is_csm_system(turn.system_run.system_type) else None, is_csm_system(turn.system_run.system_type), "offline_update_cost_only_recorded_for_csm", 0.0, 1, "total_cost.csv", "deterministic_csm_update_provider_cost_zero"))
        rows.append(obs(turn, "total_cost", cost.get("total_cost"), bool(cost.get("available")), "pricing_not_configured", cost.get("total_cost"), 1, "total_cost.csv", "versioned_provider_token_pricing"))
    else:
        rows.append(obs(turn, "tokens_per_query", None, False, "missing_llm_call", None, None, "token_results.csv", "missing_llm_call"))
        rows.append(obs(turn, "provider_generation_latency_ms", None, False, "missing_llm_call", None, None, "latency_definition_audit.csv", "missing_llm_call"))
        rows.append(obs(turn, "retrieval_activation_latency_ms", None, False, "missing_retrieval_run", None, None, "latency_definition_audit.csv", "missing_retrieval_run"))
        rows.append(obs(turn, "processing_latency_ms", None, False, "missing_llm_call", None, None, "latency_definition_audit.csv", "missing_llm_call"))
        rows.append(obs(turn, "operational_wall_clock_latency_ms", None, False, "missing_llm_call", None, None, "latency_definition_audit.csv", "missing_llm_call"))
        rows.append(obs(turn, "p95_latency", None, False, "missing_llm_call", None, None, "latency_definition_audit.csv", "missing_llm_call"))
        rows.append(obs(turn, "online_query_cost", None, False, "missing_llm_call", None, None, "total_cost.csv", "missing_llm_call"))
        rows.append(obs(turn, "offline_csm_update_cost", None, False, "missing_llm_call", None, None, "total_cost.csv", "missing_llm_call"))
        rows.append(obs(turn, "total_cost", None, False, "missing_llm_call", None, None, "total_cost.csv", "missing_llm_call"))

    contradiction_expected = bool((getattr(turn.ground_truth, "truth", {}) or {}).get("contradictions"))
    contradiction_hits = bool(getattr(turn.output, "conflicts", None))
    rows.append(obs(turn, "contradiction_handling", 1.0 if contradiction_hits else 0.0 if contradiction_expected else None, contradiction_expected, "no_ground_truth_contradiction", 1 if contradiction_hits else 0, 1 if contradiction_expected else None, "contradiction_results.csv", "stored_answer_conflict_detection"))
    return rows


def obs(turn, metric, value, applicable, reason, numerator, denominator, evidence, calculation_reason):
    return base(turn) | {
        "metric_name": metric,
        "observation_value": value,
        "applicable": bool(applicable),
        "reason_not_applicable": None if applicable else reason,
        "numerator": numerator,
        "denominator": denominator,
        "audit_file": evidence,
        "calculation_reason": calculation_reason,
    }


def is_csm_system(system_type: str) -> bool:
    return system_type in CSM_SYSTEMS


def base(turn):
    return {
        "patient": turn.patient,
        "question_id": str(turn.question.id),
        "question_number": turn.question.turn_number,
        "system": turn.system_run.system_type,
        "turn_id": str(turn.turn.id),
    }


def expected_source_ids(turn, scope: OfflineScope):
    payload = getattr(turn.ground_truth, "truth", None) or {}
    ids = set()
    scan_for_ids(payload, ids)
    return resolve_source_aliases(ids, scope)


def retrieved_source_ids(turn: OfflineTurn, csm_aliases: dict[str, str]) -> set[str]:
    retrieved_ids = set()
    for item in turn.retrieval_items:
        retrieved_ids.update(str(value) for value in (item.canonical_source_id, item.document_id, item.section_id) if value)
        native_id = str(item.system_native_id) if item.system_native_id else None
        if native_id and native_id in csm_aliases:
            retrieved_ids.add(csm_aliases[native_id])
    return retrieved_ids


def resolve_source_aliases(ids: set[str], scope: OfflineScope) -> set[str]:
    resolved = set()
    for value in ids:
        text = str(value)
        matches = scope.source_aliases.get(text)
        if matches:
            resolved.update(matches)
        else:
            resolved.add(text)
    return resolved


def scan_for_ids(value, ids):
    if isinstance(value, dict):
        for key, nested in value.items():
            if any(token in key.lower() for token in ("source", "citation", "evidence", "document", "section")):
                if isinstance(nested, list):
                    ids.update(str(item) for item in nested if isinstance(item, (str, int)))
                elif isinstance(nested, (str, int)):
                    ids.add(str(nested))
            scan_for_ids(nested, ids)
    elif isinstance(value, list):
        for item in value:
            scan_for_ids(item, ids)


def citation_f1(valid_cites, expected):
    generated = {row.resolved_id for row in valid_cites if row.resolved_id}
    if not generated or not expected:
        return None
    tp = len(generated & expected)
    precision = tp / len(generated)
    recall = tp / len(expected)
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)


def calibration_error(confidences, supports):
    if not confidences:
        return None
    accuracy = [1.0 if row["support_classification"] in {"supported", "partially_supported"} else 0.0 for row in supports]
    if not accuracy:
        return None
    return sum(abs(confidences[index] - accuracy[index]) for index in range(min(len(confidences), len(accuracy)))) / min(len(confidences), len(accuracy))


def claim_match_classification(claim, match, support_status: str) -> str:
    text = claim_text(claim).lower()
    if support_status == "insufficient_evidence_statement":
        return "insufficient_evidence_statement"
    if support_status == "not_factual":
        return "non_factual"
    if support_status == "contradicted" or "contradict" in text:
        return "contradicted"
    if match.correctness:
        return "true_positive"
    return "false_positive"


def citation_resolution_status(classification: str) -> str:
    if classification.startswith("valid"):
        return "resolved"
    if classification == "fabricated":
        return "fabricated"
    return "unresolved"


def answer_f1_row(turn: OfflineTurn, matching_rows: list[dict]) -> dict:
    tp = sum(1 for row in matching_rows if row["claim_match_classification"] == "true_positive")
    fp = sum(1 for row in matching_rows if row["claim_match_classification"] in {"false_positive", "contradicted", "unmatched"})
    fn = sum(1 for row in matching_rows if row["claim_match_classification"] == "false_negative")
    denominator_precision = tp + fp
    denominator_recall = tp + fn
    precision = tp / denominator_precision if denominator_precision else None
    recall = tp / denominator_recall if denominator_recall else None
    f1 = None
    if precision is not None and recall is not None:
        f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    applicable = f1 is not None
    return base(turn) | {
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "applicable": applicable,
        "reason_not_applicable": None if applicable else "no_generated_or_expected_factual_claims",
        "calculation_reason": "claim_level_precision_recall_f1_without_claim_id_matching",
    }


def retrieval_resolution_rows(turn: OfflineTurn, scope: OfflineScope, csm_aliases: dict[str, str]) -> list[dict]:
    expected = expected_source_ids(turn, scope)
    rows = []
    for item in turn.retrieval_items:
        native_id = str(item.system_native_id) if item.system_native_id else None
        resolved_ids = set(str(value) for value in (item.canonical_source_id, item.document_id, item.section_id) if value)
        if native_id and native_id in csm_aliases:
            resolved_ids.add(csm_aliases[native_id])
        rows.append(base(turn) | {
            "retrieval_item_id": str(item.id),
            "rank": item.rank,
            "system_native_type": item.system_native_type,
            "system_native_id": native_id,
            "canonical_source_id": str(item.canonical_source_id) if item.canonical_source_id else None,
            "resolved_canonical_ids": sorted(resolved_ids),
            "expected_canonical_ids": sorted(expected),
            "resolution_status": "resolved" if resolved_ids else "unresolved",
            "relevance_classification": "relevant" if resolved_ids & expected else "not_relevant",
            "relevant": bool(resolved_ids & expected),
            "calculation_reason": "retrieval_identifier_canonicalized_with_csm_state_aliases" if is_csm_system(turn.system_run.system_type) else "retrieval_identifier_canonicalized",
        })
    return rows
