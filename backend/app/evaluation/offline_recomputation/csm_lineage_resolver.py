from __future__ import annotations

from collections import defaultdict

from app.evaluation.offline_recomputation.scope_loader import CsmBundle


def csm_alias_map(bundle: CsmBundle) -> dict[str, str]:
    evidence_by_id = {row.id: row for row in bundle.evidence}
    aliases = {}
    for index, state in enumerate(bundle.states, start=1):
        linked_sources = []
        for link in bundle.links:
            if link.state_variable_id == state.id:
                evidence = evidence_by_id.get(link.evidence_id)
                if evidence:
                    linked_sources.append(str(evidence.canonical_source_id))
        if linked_sources:
            primary = linked_sources[0]
            aliases[str(state.id)] = primary
            aliases[f"state:{state.state_key}"] = primary
            aliases[f"state_{index}"] = primary
            aliases[f"C{index}"] = primary
    return aliases


def csm_state_trace(bundle: CsmBundle) -> list[dict]:
    histories = defaultdict(list)
    for history in bundle.history:
        histories[history.state_variable_id].append(history)
    return [
        {
            "state_id": str(state.id),
            "state_type": state.state_type,
            "state_key": state.state_key,
            "current_value": state.current_value,
            "status": state.status,
            "current_version": state.current_version,
            "valid_from": iso(state.valid_from),
            "valid_to": iso(state.valid_to),
            "history": [
                {
                    "version_number": item.version_number,
                    "previous_value": item.previous_value,
                    "new_value": item.new_value,
                    "update_reason": item.update_reason,
                    "created_at": iso(item.created_at),
                }
                for item in sorted(histories[state.id], key=lambda row: row.version_number)
            ],
        }
        for state in bundle.states
    ]


def csm_lineage_trace(bundle: CsmBundle) -> list[dict]:
    evidence_by_id = {row.id: row for row in bundle.evidence}
    state_by_id = {row.id: row for row in bundle.states}
    rows = []
    for link in bundle.links:
        evidence = evidence_by_id.get(link.evidence_id)
        state = state_by_id.get(link.state_variable_id)
        rows.append(
            {
                "state_id": str(link.state_variable_id),
                "state_key": state.state_key if state else None,
                "evidence_id": str(link.evidence_id),
                "canonical_source_id": str(evidence.canonical_source_id) if evidence else None,
                "source_type": evidence.source_type if evidence else None,
                "verification_status": evidence.verification_status if evidence else None,
                "contribution_type": link.contribution_type,
                "contribution_weight": link.contribution_weight,
            }
        )
    return rows


def activation_audit_rows(bundle: CsmBundle) -> list[dict]:
    runs = {run.id: run for run in bundle.activation_runs}
    evidence_by_id = {row.id: row for row in bundle.evidence}
    linked_evidence = defaultdict(list)
    for link in bundle.links:
        evidence = evidence_by_id.get(link.evidence_id)
        if evidence:
            linked_evidence[link.state_variable_id].append(evidence)
    rows = []
    for item in bundle.activation_items:
        evidence_rows = linked_evidence.get(item.state_variable_id, [])
        rows.append(
            {
                "activation_run_id": str(item.activation_run_id),
                "query_text": runs[item.activation_run_id].query_text if item.activation_run_id in runs else None,
                "state_variable_id": str(item.state_variable_id),
                "linked_evidence_ids": [str(evidence.id) for evidence in evidence_rows],
                "linked_canonical_source_ids": [str(evidence.canonical_source_id) for evidence in evidence_rows],
                "rank": item.rank,
                "selected": item.selected,
                "relevance_score": item.relevance_score,
                "dependency_score": item.dependency_score,
                "confidence_score": item.confidence_score,
                "utility_score": item.utility_score,
                "estimated_token_cost": item.estimated_token_cost,
                "selection_reason": item.selection_reason,
                "calculation_reason": "activated_state_resolved_through_csm_state_evidence_links",
            }
        )
    return rows


def dependency_trace_rows(bundle: CsmBundle) -> list[dict]:
    state_by_id = {row.id: row for row in bundle.states}
    return [
        {
            "dependency_id": str(row.id),
            "source_state_id": str(row.source_state_id),
            "source_state_key": state_by_id[row.source_state_id].state_key if row.source_state_id in state_by_id else None,
            "target_state_id": str(row.target_state_id),
            "target_state_key": state_by_id[row.target_state_id].state_key if row.target_state_id in state_by_id else None,
            "relation_type": row.relation_type,
            "weight": row.weight,
            "decay": row.decay,
            "status": row.status,
        }
        for row in bundle.dependencies
    ]


def iso(value):
    return value.isoformat() if value else None
