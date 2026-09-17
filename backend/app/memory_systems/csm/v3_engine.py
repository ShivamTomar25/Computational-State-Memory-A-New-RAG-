from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from app.memory_systems.common.embeddings.providers import (
    DeterministicEmbeddingProvider,
    cosine_similarity,
)
from app.memory_systems.common.registry.adapter import source_preview
from app.memory_systems.common.token_budget.service import estimate_tokens
from app.memory_systems.csm.models import CsmEvidence, CsmStateHistory, CsmStateVariable


CSM_V3_IMPLEMENTATION_VERSION = "csm_v3"
CSM_V3_STATE_SCHEMA_VERSION = "csm_state_schema_v3"

CSM_LIKE_SYSTEM_TYPES = {"csm", "csm_v3"}

CURRENT_STATE_ROUTES = {
    "state_first",
    "decision_state",
    "high_risk_review",
    "hybrid_state_evidence",
    "dependency_state",
}
HISTORICAL_ROUTES = {"temporal_state", "correction_state"}
EVIDENCE_FIRST_ROUTES = {"exact_source", "evidence_first", "rare_detail"}

HIGH_RISK_TERMS = {
    "allergy",
    "allergic",
    "anaphylaxis",
    "contraindication",
    "contraindicated",
    "diagnosis",
    "discontinue",
    "dose",
    "dosage",
    "emergency",
    "medication",
    "stop",
    "treatment",
    "urgent",
}
TEMPORAL_TERMS = {
    "after",
    "before",
    "change",
    "changed",
    "current",
    "currently",
    "history",
    "latest",
    "now",
    "previous",
    "prior",
    "timeline",
    "trend",
    "when",
}
CORRECTION_TERMS = {
    "addendum",
    "amended",
    "corrected",
    "correction",
    "corrects",
    "replaced",
    "revised",
    "superseded",
    "updated",
}
DEPENDENCY_TERMS = {
    "affect",
    "because",
    "depend",
    "dependency",
    "downstream",
    "impact",
    "propagate",
    "recompute",
    "related",
}
DECISION_TERMS = {
    "action",
    "decision",
    "follow-up",
    "followup",
    "next",
    "recommend",
    "review",
    "should",
}
SOURCE_TERMS = {
    "citation",
    "document",
    "evidence",
    "page",
    "quote",
    "source",
    "where",
}
EVIDENCE_TERMS = {
    "lab",
    "labs",
    "note",
    "record",
    "report",
    "result",
}
RENAL_TERMS = {"creatinine", "egfr", "gfr", "kidney", "renal"}


@dataclass(frozen=True)
class StateDefinition:
    state_type: str
    semantic_type: str
    accepted_source_types: tuple[str, ...]
    accepted_source_subtypes: tuple[str, ...]
    key_fields: tuple[str, ...]
    value_fields: tuple[str, ...]
    update_operator: str
    temporal_policy: str
    contradiction_policy: str
    lifecycle_policy: str
    serialization_policy: str
    dependency_rules: tuple[str, ...] = ()
    derived: bool = False


@dataclass(frozen=True)
class QueryRoute:
    mode: str
    features: dict[str, Any]
    reason: str
    include_historical: bool
    evidence_fallback: bool
    preferred_state_types: tuple[str, ...]
    preferred_evidence_types: tuple[str, ...]
    mandatory_policy: str


STATE_DEFINITIONS: dict[str, StateDefinition] = {
    "condition": StateDefinition(
        state_type="condition",
        semantic_type="clinical_condition_status",
        accepted_source_types=("patient_information",),
        accepted_source_subtypes=("condition",),
        key_fields=("name",),
        value_fields=("name", "category", "clinical_status", "verification_status", "severity", "onset_date", "resolved_date"),
        update_operator="typed_condition_lifecycle_update_v3",
        temporal_policy="valid_time_latest_recorded_version",
        contradiction_policy="conversation_cannot_confirm_condition",
        lifecycle_policy="active_candidate_contested_resolved",
        serialization_policy="compact_decision_state",
        dependency_rules=("medication_condition_same_reason",),
    ),
    "medication": StateDefinition(
        state_type="medication",
        semantic_type="medication_exposure_status",
        accepted_source_types=("patient_information",),
        accepted_source_subtypes=("medication",),
        key_fields=("medication_name", "generic_name"),
        value_fields=("medication_name", "generic_name", "dosage_value", "dosage_unit", "frequency", "route", "medication_status", "start_date", "end_date", "reason"),
        update_operator="typed_medication_effective_time_update_v3",
        temporal_policy="effective_time_status_update",
        contradiction_policy="stopped_or_entered_in_error_supersedes_active",
        lifecycle_policy="active_stopped_pending_resolved",
        serialization_policy="compact_decision_state",
        dependency_rules=("allergy_medication_same_substance",),
    ),
    "allergy": StateDefinition(
        state_type="allergy",
        semantic_type="allergy_status",
        accepted_source_types=("patient_information",),
        accepted_source_subtypes=("allergy",),
        key_fields=("substance",),
        value_fields=("substance", "allergy_type", "category", "clinical_status", "verification_status", "criticality", "reaction", "severity"),
        update_operator="typed_allergy_verification_update_v3",
        temporal_policy="latest_verified_allergy_state",
        contradiction_policy="challenge_or_entered_in_error_contests_prior",
        lifecycle_policy="historical_unverified_confirmed_contested_resolved",
        serialization_policy="compact_safety_state",
        dependency_rules=("allergy_medication_same_substance",),
    ),
    "measurement": StateDefinition(
        state_type="measurement",
        semantic_type="decision_relevant_measurement",
        accepted_source_types=("patient_information",),
        accepted_source_subtypes=("measurement",),
        key_fields=("observation_name",),
        value_fields=("observation_name", "value_numeric", "value_text", "unit", "observed_at", "status", "interpretation", "notes"),
        update_operator="typed_measurement_temporal_update_v3",
        temporal_policy="valid_time_ordered_corrected_measurement",
        contradiction_policy="corrected_measurement_supersedes_prior_same_key",
        lifecycle_policy="active_corrected_superseded_entered_in_error",
        serialization_policy="compact_numeric_state",
        dependency_rules=("measurement_trend", "renal_function_if_renal_measurement"),
    ),
    "measurement_trend": StateDefinition(
        state_type="measurement_trend",
        semantic_type="derived_measurement_trend",
        accepted_source_types=(),
        accepted_source_subtypes=(),
        key_fields=("observation_name",),
        value_fields=("direction", "latest_value", "previous_value", "unit", "latest_valid_time", "previous_valid_time"),
        update_operator="deterministic_measurement_trend_recompute_v3",
        temporal_policy="recompute_from_measurement_history",
        contradiction_policy="derived_state_stale_if_parent_unresolved",
        lifecycle_policy="active_or_stale",
        serialization_policy="compact_derived_state",
        dependency_rules=("measurement_parent",),
        derived=True,
    ),
    "renal_function": StateDefinition(
        state_type="renal_function",
        semantic_type="derived_renal_function_state",
        accepted_source_types=(),
        accepted_source_subtypes=(),
        key_fields=("renal_function",),
        value_fields=("basis", "latest_measurement", "unit", "direction", "valid_time"),
        update_operator="deterministic_renal_measurement_recompute_v3",
        temporal_policy="recompute_from_renal_measurement_state",
        contradiction_policy="derived_state_stale_if_parent_unresolved",
        lifecycle_policy="active_or_stale",
        serialization_policy="compact_derived_state",
        dependency_rules=("renal_measurement_parent",),
        derived=True,
    ),
}

CSM_V3_SCORE_WEIGHTS = {
    "semantic_relevance": 0.18,
    "lexical_relevance": 0.24,
    "state_confidence": 0.12,
    "evidence_quality": 0.12,
    "current_version": 0.10,
    "temporal": 0.08,
    "dependency": 0.06,
    "uncertainty_reduction": 0.04,
    "governance": 0.04,
    "route": 0.08,
    "recency": 0.04,
    "redundancy_penalty": -0.08,
    "serialization_cost": -0.04,
}

_EMBEDDINGS = DeterministicEmbeddingProvider(dimension=64)


def route_query_v3(query: str) -> QueryRoute:
    lowered = (query or "").lower()
    terms = tokenize(lowered)
    has_number = bool(re.search(r"\b\d+(?:\.\d+)?\b", lowered))
    has_date = bool(re.search(r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|\d{4}-\d{2}-\d{2}|\d{1,2}\s+[a-z]+)\b", lowered))
    features = {
        "high_risk_terms": sorted(terms & HIGH_RISK_TERMS),
        "temporal_terms": sorted(terms & TEMPORAL_TERMS),
        "correction_terms": sorted(terms & CORRECTION_TERMS),
        "dependency_terms": sorted(terms & DEPENDENCY_TERMS),
        "decision_terms": sorted(terms & DECISION_TERMS),
        "source_terms": sorted(terms & SOURCE_TERMS),
        "evidence_terms": sorted(terms & EVIDENCE_TERMS),
        "renal_terms": sorted(terms & RENAL_TERMS),
        "has_number": has_number,
        "has_date": has_date,
        "token_count": len(terms),
    }
    historical_temporal_terms = set(features["temporal_terms"]) - {"current", "currently", "latest", "now"}

    if features["high_risk_terms"] and (features["decision_terms"] or "should" in terms):
        mode = "high_risk_review"
        reason = "high_risk_decision_terms"
    elif features["correction_terms"]:
        mode = "correction_state"
        reason = "correction_or_supersession_terms"
    elif features["dependency_terms"]:
        mode = "dependency_state"
        reason = "dependency_or_propagation_terms"
    elif historical_temporal_terms or has_date:
        mode = "temporal_state"
        reason = "temporal_terms_or_explicit_date"
    elif features["source_terms"]:
        mode = "exact_source"
        reason = "source_or_citation_terms"
    elif features["decision_terms"]:
        mode = "decision_state"
        reason = "decision_or_action_terms"
    elif features["evidence_terms"]:
        mode = "evidence_first"
        reason = "raw_evidence_terms"
    elif has_number or len(terms) <= 5:
        mode = "rare_detail"
        reason = "short_query_or_numeric_detail"
    elif {"summary", "summarize", "course", "overall"} & terms:
        mode = "hybrid_state_evidence"
        reason = "summary_requires_state_and_evidence"
    else:
        mode = "state_first"
        reason = "default_current_state_lookup"

    return QueryRoute(
        mode=mode,
        features=features,
        reason=reason,
        include_historical=mode in HISTORICAL_ROUTES,
        evidence_fallback=mode in EVIDENCE_FIRST_ROUTES or mode in {"correction_state", "hybrid_state_evidence"},
        preferred_state_types=preferred_state_types_v3(terms, mode),
        preferred_evidence_types=preferred_evidence_types_v3(terms, mode),
        mandatory_policy=mandatory_policy_for_route(mode),
    )


def preferred_state_types_v3(terms: set[str], mode: str) -> tuple[str, ...]:
    selected: list[str] = []
    if {"condition", "conditions", "diagnosis", "diagnoses", "problem", "problems"} & terms:
        selected.append("condition")
    if {"medication", "medications", "drug", "dose", "dosage", "prescription"} & terms:
        selected.append("medication")
    if {"allergy", "allergies", "reaction", "allergic"} & terms:
        selected.append("allergy")
    if {"lab", "labs", "measurement", "value", "result", "egfr", "creatinine", "potassium"} & terms:
        selected.append("measurement")
    if {"trend", "improved", "worse", "increased", "decreased"} & terms:
        selected.append("measurement_trend")
    if terms & RENAL_TERMS:
        selected.extend(["renal_function", "measurement", "measurement_trend"])
    if mode == "high_risk_review":
        selected.extend(["allergy", "medication", "condition"])
    if mode in {"temporal_state", "correction_state"}:
        selected.extend(["measurement", "measurement_trend", "condition", "medication", "allergy"])
    if mode == "dependency_state":
        selected.extend(["measurement", "measurement_trend", "renal_function", "medication", "allergy", "condition"])
    return tuple(dict.fromkeys(selected))


def preferred_evidence_types_v3(terms: set[str], mode: str) -> tuple[str, ...]:
    selected: list[str] = []
    if {"document", "report", "page", "source", "evidence", "citation", "quote"} & terms:
        selected.extend(["document_evidence", "document_section_evidence", "document_text_evidence"])
    if {"note", "notes"} & terms:
        selected.extend(["structured_clinical_note", "document_section_evidence"])
    if {"lab", "labs", "measurement", "result", "value", "creatinine", "egfr"} & terms:
        selected.extend(["structured_measurement", "document_section_evidence"])
    if mode in EVIDENCE_FIRST_ROUTES or mode == "correction_state":
        selected.extend(["document_evidence", "document_section_evidence", "structured_measurement", "structured_clinical_note"])
    return tuple(dict.fromkeys(selected))


def mandatory_policy_for_route(mode: str) -> str:
    return {
        "state_first": "best_current_state_plus_primary_support",
        "temporal_state": "ordered_relevant_state_versions",
        "correction_state": "current_state_superseded_state_correction_evidence",
        "dependency_state": "selected_state_and_bounded_dependencies",
        "decision_state": "decision_state_and_safety_support",
        "evidence_first": "best_evidence",
        "exact_source": "exact_source_evidence",
        "rare_detail": "rare_detail_evidence_fallback",
        "hybrid_state_evidence": "state_summary_plus_best_evidence",
        "high_risk_review": "safety_state_and_verification_evidence",
    }.get(mode, "best_current_state_plus_primary_support")


def state_definition_for_source(source) -> Optional[StateDefinition]:
    for definition in STATE_DEFINITIONS.values():
        if definition.derived:
            continue
        if source.source_type in definition.accepted_source_types and source.source_subtype in definition.accepted_source_subtypes:
            return definition
    return None


def evidence_type_for_source_v3(source) -> str:
    if source.source_type == "patient_information":
        return f"structured_{source.source_subtype}"
    if source.source_type == "conversation":
        return "conversation_unverified_claim"
    if source.source_type == "document" and source.source_subtype == "document":
        return "document_evidence"
    if source.source_type == "document" and source.source_subtype == "section":
        return "document_section_evidence"
    if source.source_type == "document" and source.source_subtype == "page":
        return "document_page_evidence"
    if source.source_type == "document":
        return "document_text_evidence"
    return f"{source.source_type}_evidence"


def verification_status_for_source_v3(source) -> str:
    if source.source_type == "patient_information":
        payload = source.structured_payload or {}
        verification = str(payload.get("verification_status") or payload.get("status") or "").lower()
        if verification in {"entered-in-error", "refuted", "cancelled"}:
            return "contested"
        return "verified"
    if source.source_type == "conversation":
        return "pending_review"
    return "candidate"


def confidence_for_source_v3(source) -> float:
    if source.source_type == "patient_information":
        payload = source.structured_payload or {}
        status_text = str(payload.get("verification_status") or payload.get("status") or "").lower()
        if status_text in {"entered-in-error", "refuted", "cancelled"}:
            return 0.72
        return 0.95
    if source.source_type == "document":
        return 0.68 if source.source_subtype in {"section", "page", "extracted_text"} else 0.55
    if source.source_type == "conversation":
        return 0.20
    return 0.4


def state_key_for_source_v3(source) -> str:
    definition = state_definition_for_source(source)
    payload = source.structured_payload or {}
    if definition is None:
        return f"evidence_only:{source.source_type}:{source.source_subtype}:{source.source_record_id}"
    key_value = first_payload_value(payload, definition.key_fields) or source.source_record_id
    return f"{definition.state_type}:{normalize_key(key_value)}"


def first_payload_value(payload: dict[str, Any], fields: tuple[str, ...]) -> Optional[str]:
    for field in fields:
        value = payload.get(field)
        if value not in (None, ""):
            return str(value)
    return None


def source_observed_value(source, definition: StateDefinition) -> dict[str, Any]:
    payload = source.structured_payload or {}
    value = {field: payload.get(field) for field in definition.value_fields if payload.get(field) is not None}
    if definition.state_type == "measurement":
        value["display"] = measurement_display(payload, source.content_text)
    elif definition.state_type == "medication":
        value["display"] = medication_display(payload, source.content_text)
    elif definition.state_type == "allergy":
        value["display"] = allergy_display(payload, source.content_text)
    elif definition.state_type == "condition":
        value["display"] = condition_display(payload, source.content_text)
    else:
        value["display"] = source_preview(source.content_text, max_length=180)
    return value


def lifecycle_status_for_source_v3(source, definition: StateDefinition, evidence: CsmEvidence) -> str:
    payload = source.structured_payload or {}
    status_values = " ".join(
        str(payload.get(key) or "")
        for key in ("clinical_status", "medication_status", "status", "verification_status")
    ).lower()
    text = f"{status_values} {source.content_text}".lower()

    if any(term in text for term in ("entered-in-error", "entered in error", "cancelled", "canceled", "refuted")):
        return "contested"
    if any(term in text for term in ("resolved", "inactive", "stopped", "completed")) or payload.get("end_date") or payload.get("resolved_date"):
        return "resolved" if definition.state_type in {"condition", "allergy"} else "inactive"
    if evidence.verification_status == "pending_review":
        return "pending_review"
    if evidence.verification_status == "candidate":
        return "candidate"
    if definition.state_type == "allergy" and "unconfirmed" in text:
        return "unverified"
    return "active"


def transition_operation_v3(
    *,
    previous_value: Optional[dict[str, Any]],
    source,
    evidence: CsmEvidence,
) -> str:
    if previous_value is None:
        return "initialize"
    if is_correction_source(source):
        return "correct"
    lineage = previous_value.get("lineage") or {}
    if lineage.get("source_hash") == source.content_hash:
        return "idempotent"
    previous_recorded = parse_iso(previous_value.get("recorded_time"))
    current_recorded = source.recorded_time
    if previous_recorded and current_recorded and current_recorded < previous_recorded:
        return "late_arriving_historical_evidence"
    return "supersede"


def build_state_value_payload_v3(
    *,
    source,
    evidence: CsmEvidence,
    definition: StateDefinition,
    operation: str,
    version: int,
    previous_value: Optional[dict[str, Any]],
    supersedes: list[str],
    dependency_ids: list[str],
) -> dict[str, Any]:
    structured = dict(source.structured_payload or {})
    value = source_observed_value(source, definition)
    lifecycle_status = lifecycle_status_for_source_v3(source, definition, evidence)
    evidence_id = str(evidence.id)
    previous_support = set(previous_value.get("support_evidence_ids") or []) if previous_value else set()
    previous_corrections = set(previous_value.get("correction_evidence_ids") or []) if previous_value else set()
    support_evidence_ids = set(previous_support)
    correction_evidence_ids = set(previous_corrections)

    if operation == "correct":
        correction_evidence_ids.add(evidence_id)
    else:
        support_evidence_ids.add(evidence_id)

    return {
        "schema_version": CSM_V3_STATE_SCHEMA_VERSION,
        "implementation_version": CSM_V3_IMPLEMENTATION_VERSION,
        "state_identity": {
            "state_type": definition.state_type,
            "semantic_type": definition.semantic_type,
            "state_key": state_key_for_source_v3(source),
            "source_subtype": source.source_subtype,
        },
        "value": value,
        "raw_value": source_preview(source.content_text, max_length=500),
        "structured": structured,
        "unit": structured.get("unit") or structured.get("dosage_unit"),
        "status": lifecycle_status,
        "valid_time": source.valid_time.isoformat() if source.valid_time else None,
        "recorded_time": source.recorded_time.isoformat() if source.recorded_time else None,
        "event_time": source.event_time.isoformat() if getattr(source, "event_time", None) else None,
        "recorded_source_ids": sorted(
            set(previous_value.get("recorded_source_ids") or []) | {str(source.id)}
            if previous_value
            else {str(source.id)}
        ),
        "evidence_ids": sorted(
            set(previous_value.get("evidence_ids") or []) | {evidence_id}
            if previous_value
            else {evidence_id}
        ),
        "support_evidence_ids": sorted(support_evidence_ids),
        "correction_evidence_ids": sorted(correction_evidence_ids),
        "lineage": {
            "latest_canonical_source_id": str(source.id),
            "latest_evidence_id": evidence_id,
            "document_id": str(source.document_id) if source.document_id else None,
            "page_number": source.page_number,
            "section_id": str(source.section_id) if source.section_id else None,
            "source_hash": source.content_hash,
            "source_type": source.source_type,
            "source_subtype": source.source_subtype,
        },
        "relations": {
            "incoming_relation": relation_for_transition(operation, evidence),
            "supports": sorted(support_evidence_ids),
            "corrects": sorted(correction_evidence_ids),
            "supersedes": sorted(set(supersedes)),
            "superseded_by": [],
        },
        "confidence_components": {
            "source_confidence": float(evidence.confidence),
            "verification_quality": verification_quality(evidence.verification_status),
            "structure_quality": 1.0 if structured else 0.60,
            "operator_quality": operator_quality(operation),
        },
        "uncertainty_components": uncertainty_components_v3(source, evidence, lifecycle_status),
        "dependency_ids": sorted(set(dependency_ids)),
        "transition": {
            "operation": operation,
            "operator": definition.update_operator,
            "reason": update_reason_v3(definition, operation),
            "previous_version": version - 1 if version > 1 else None,
            "new_version": version,
            "valid_time": source.valid_time.isoformat() if source.valid_time else None,
            "recorded_time": source.recorded_time.isoformat() if source.recorded_time else None,
        },
        "audit": {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "state_schema_registry": "explicit_state_definitions_v3",
            "temporal_policy": definition.temporal_policy,
            "contradiction_policy": definition.contradiction_policy,
            "lifecycle_policy": definition.lifecycle_policy,
            "serialization_policy": definition.serialization_policy,
            "requires_review": evidence.verification_status == "pending_review",
            "llm_mutable": False,
        },
    }


def build_superseded_previous_value(previous_value: Optional[dict[str, Any]], *, evidence_id: str, operation: str) -> Optional[dict[str, Any]]:
    if not previous_value:
        return previous_value
    updated = dict(previous_value)
    relations = dict(updated.get("relations") or {})
    superseded_by = set(relations.get("superseded_by") or updated.get("superseded_by") or [])
    superseded_by.add(evidence_id)
    relations["superseded_by"] = sorted(superseded_by)
    updated["relations"] = relations
    updated["status"] = "superseded" if operation in {"correct", "supersede"} else updated.get("status")
    return updated


def relation_for_transition(operation: str, evidence: CsmEvidence) -> str:
    if operation == "correct":
        return "CORRECTS"
    if operation == "supersede":
        return "SUPERSEDES"
    if operation == "late_arriving_historical_evidence":
        return "QUALIFIES"
    if evidence.verification_status == "pending_review":
        return "QUALIFIES"
    if evidence.verification_status == "contested":
        return "CONTRADICTS"
    return "SUPPORTS"


def update_reason_v3(definition: StateDefinition, operation: str) -> str:
    return f"{definition.update_operator}:{operation}"


def operator_quality(operation: str) -> float:
    return {
        "initialize": 0.95,
        "supersede": 0.90,
        "correct": 0.92,
        "late_arriving_historical_evidence": 0.78,
        "derived_recompute": 0.86,
        "idempotent": 1.0,
    }.get(operation, 0.75)


def uncertainty_components_v3(source, evidence: CsmEvidence, lifecycle_status: str) -> dict[str, float]:
    confidence = max(0.0, min(1.0, float(evidence.confidence or 0.0)))
    verification_uncertainty = 1.0 - verification_quality(evidence.verification_status)
    temporal_uncertainty = 0.04 if source.valid_time else 0.20
    lifecycle_uncertainty = 0.20 if lifecycle_status in {"candidate", "unverified", "pending_review", "contested"} else 0.06
    return {
        "posterior_uncertainty": min(1.0, (1.0 - confidence) + lifecycle_uncertainty),
        "verification_uncertainty": verification_uncertainty,
        "temporal_uncertainty": temporal_uncertainty,
        "lifecycle_uncertainty": lifecycle_uncertainty,
    }


def verification_quality(status: str) -> float:
    return {
        "verified": 1.0,
        "candidate": 0.68,
        "pending_review": 0.28,
        "contested": 0.45,
    }.get(status, 0.50)


def is_correction_source(source) -> bool:
    payload = source.structured_payload or {}
    text = " ".join(
        str(value or "")
        for value in (
            source.content_text,
            payload.get("status"),
            payload.get("verification_status"),
            payload.get("notes"),
            payload.get("interpretation"),
        )
    ).lower()
    return bool(tokenize(text) & CORRECTION_TERMS) or any(
        marker in text
        for marker in ("entered-in-error", "entered in error", "corrected", "amended", "revised")
    )


def allow_state_for_route_v3(
    *,
    state: CsmStateVariable,
    route: QueryRoute,
    cutoff_time: Optional[datetime],
) -> tuple[bool, str]:
    value = state.current_value or {}
    if value.get("implementation_version") != CSM_V3_IMPLEMENTATION_VERSION:
        return False, "non_v3_state"
    recorded_time = parse_iso(value.get("recorded_time"))
    if cutoff_time and recorded_time and recorded_time > cutoff_time:
        return False, "recorded_after_source_cutoff"
    status = (value.get("status") or state.status or "").lower()
    if status in {"superseded"} and not route.include_historical:
        return False, "superseded_excluded_for_current_query"
    if state.status not in {"active", "candidate", "stale", "contested"} and not route.include_historical:
        return False, "inactive_nonhistorical_state"
    if state.status == "candidate" and route.mode in {"state_first", "decision_state"}:
        return False, "candidate_state_excluded_for_current_decision_query"
    return True, "allowed"


def allow_evidence_for_route_v3(
    *,
    evidence: CsmEvidence,
    route: QueryRoute,
    cutoff_time: Optional[datetime],
) -> tuple[bool, str]:
    if evidence.structured_value.get("csm_implementation_version") != CSM_V3_IMPLEMENTATION_VERSION:
        return False, "non_v3_evidence"
    if cutoff_time and evidence.recorded_time and evidence.recorded_time > cutoff_time:
        return False, "recorded_after_source_cutoff"
    lifecycle = str(evidence.structured_value.get("csm_v3_lifecycle") or "current")
    if lifecycle == "obsolete" and not route.include_historical and not route.evidence_fallback:
        return False, "obsolete_evidence_excluded_for_current_query"
    if evidence.verification_status == "pending_review" and route.mode in {"state_first", "decision_state"}:
        return False, "pending_review_evidence_excluded_for_current_query"
    return True, "allowed"


def score_state_v3(
    *,
    query: str,
    query_terms: set[str],
    route: QueryRoute,
    state: CsmStateVariable,
    evidence: Optional[CsmEvidence],
    dependency_score: float,
    cutoff_time: Optional[datetime],
    redundant: bool = False,
    historical: bool = False,
) -> tuple[float, dict[str, float], str]:
    value = state.current_value or {}
    text = f"{state.state_type} {state.state_key} {value.get('value')} {value.get('raw_value')} {value.get('structured')}"
    semantic = semantic_relevance(query, text)
    lexical = lexical_relevance(query_terms, tokenize(text))
    confidence = bounded_float(state.confidence)
    evidence_quality = verification_quality(evidence.verification_status) if evidence else 0.55
    current_version = 0.45 if historical else current_version_score(state)
    temporal = temporal_score(
        recorded_time=parse_iso(value.get("recorded_time")),
        valid_time=parse_iso(value.get("valid_time")) or state.valid_from,
        cutoff_time=cutoff_time,
        route=route,
    )
    uncertainty = uncertainty_reduction_score(value.get("uncertainty_components") or {})
    governance = governance_score(value.get("status") or state.status, route, relation_text=value.get("relations"))
    route_score = route_state_bonus_v3(route, state)
    recency = recency_score(parse_iso(value.get("valid_time")) or state.valid_from)
    token_cost = serialization_cost_score(estimate_tokens(compact_state_context_v3(state=state, evidence=evidence, route=route, components={})))
    redundancy = 1.0 if redundant else 0.0
    components = {
        "semantic_relevance": semantic,
        "lexical_relevance": lexical,
        "state_confidence": confidence,
        "evidence_quality": evidence_quality,
        "current_version": current_version,
        "temporal": temporal,
        "dependency": dependency_score,
        "uncertainty_reduction": uncertainty,
        "governance": governance,
        "route": route_score,
        "recency": recency,
        "redundancy_penalty": redundancy,
        "serialization_cost": token_cost,
    }
    utility = weighted_utility(components)
    reason = "mandatory_state_candidate" if is_direct_state_match(route, state, lexical, semantic) else "optional_state_candidate"
    return utility, components, reason


def score_evidence_v3(
    *,
    query: str,
    query_terms: set[str],
    route: QueryRoute,
    evidence: CsmEvidence,
    cutoff_time: Optional[datetime],
    redundant: bool = False,
) -> tuple[float, dict[str, float], str]:
    text = f"{evidence.evidence_type} {evidence.observation_type} {evidence.normalized_value or ''} {evidence.content}"
    semantic = semantic_relevance(query, text)
    lexical = lexical_relevance(query_terms, tokenize(text))
    confidence = bounded_float(evidence.confidence)
    evidence_quality = verification_quality(evidence.verification_status)
    temporal = temporal_score(
        recorded_time=evidence.recorded_time,
        valid_time=evidence.valid_time,
        cutoff_time=cutoff_time,
        route=route,
    )
    governance = governance_score(evidence.verification_status, route, relation_text=evidence.structured_value)
    route_score = route_evidence_bonus_v3(route, evidence)
    recency = recency_score(evidence.valid_time or evidence.recorded_time)
    token_cost = serialization_cost_score(estimate_tokens(compact_evidence_context_v3(evidence=evidence, route=route, components={})))
    redundancy = 1.0 if redundant else 0.0
    components = {
        "semantic_relevance": semantic,
        "lexical_relevance": lexical,
        "state_confidence": confidence,
        "evidence_quality": evidence_quality,
        "current_version": 1.0,
        "temporal": temporal,
        "dependency": 0.0,
        "uncertainty_reduction": 0.0,
        "governance": governance,
        "route": route_score,
        "recency": recency,
        "redundancy_penalty": redundancy,
        "serialization_cost": token_cost,
    }
    utility = weighted_utility(components)
    reason = "mandatory_evidence_candidate" if route.mode in EVIDENCE_FIRST_ROUTES and (lexical >= 0.05 or semantic >= 0.20) else "optional_evidence_candidate"
    return utility, components, reason


def weighted_utility(components: dict[str, float]) -> float:
    score = 0.0
    for key, weight in CSM_V3_SCORE_WEIGHTS.items():
        score += components.get(key, 0.0) * weight
    return max(0.0, min(1.0, score))


def semantic_relevance(query: str, text: str) -> float:
    if not query or not text:
        return 0.0
    return max(0.0, min(1.0, cosine_similarity(_EMBEDDINGS.embed_query(query), _EMBEDDINGS.embed_query(text))))


def lexical_relevance(query_terms: set[str], candidate_terms: set[str]) -> float:
    if not query_terms or not candidate_terms:
        return 0.0
    expanded = expand_terms(query_terms)
    return len(expanded & candidate_terms) / max(1, len(expanded))


def expand_terms(terms: set[str]) -> set[str]:
    expanded = set(terms)
    synonyms = {
        "kidney": {"renal", "creatinine", "egfr", "gfr"},
        "renal": {"kidney", "creatinine", "egfr", "gfr"},
        "lab": {"measurement", "result", "report"},
        "labs": {"measurement", "result", "report"},
        "medicine": {"medication", "drug"},
        "medications": {"medication", "drug"},
        "followup": {"follow", "up", "follow-up"},
        "source": {"evidence", "document", "citation"},
        "corrected": {"correction", "amended", "revised"},
    }
    for term in list(terms):
        expanded.update(synonyms.get(term, set()))
    return expanded


def current_version_score(state: CsmStateVariable) -> float:
    value = state.current_value or {}
    status = str(value.get("status") or state.status or "").lower()
    if status == "superseded":
        return 0.0
    if state.status == "active":
        return 1.0
    if state.status in {"contested", "stale"}:
        return 0.72
    if state.status == "candidate":
        return 0.55
    return 0.30


def temporal_score(
    *,
    recorded_time: Optional[datetime],
    valid_time: Optional[datetime],
    cutoff_time: Optional[datetime],
    route: QueryRoute,
) -> float:
    if cutoff_time and recorded_time and recorded_time > cutoff_time:
        return 0.0
    if route.include_historical and valid_time:
        return 0.85
    if valid_time is None:
        return 0.55
    return 0.80


def uncertainty_reduction_score(uncertainty: dict[str, Any]) -> float:
    if not uncertainty:
        return 0.45
    posterior = bounded_float(uncertainty.get("posterior_uncertainty"), default=0.50)
    return max(0.0, min(1.0, 1.0 - posterior))


def governance_score(status: str, route: QueryRoute, relation_text: Any = None) -> float:
    text = f"{status} {relation_text}".lower()
    if route.mode == "correction_state" and any(term in text for term in ("correct", "supersede", "contradict", "contest")):
        return 1.0
    if route.mode == "high_risk_review" and any(term in text for term in HIGH_RISK_TERMS):
        return 0.85
    if status in {"contested", "pending_review", "unverified"}:
        return 0.70
    return 0.45


def route_state_bonus_v3(route: QueryRoute, state: CsmStateVariable) -> float:
    value = state.current_value or {}
    semantic = (value.get("state_identity") or {}).get("semantic_type")
    if state.state_type in route.preferred_state_types or semantic in route.preferred_state_types:
        return 1.0
    if route.mode in CURRENT_STATE_ROUTES and state.state_type in {"condition", "medication", "allergy", "measurement", "measurement_trend", "renal_function"}:
        return 0.55
    if route.mode in EVIDENCE_FIRST_ROUTES:
        return 0.20
    return 0.35


def route_evidence_bonus_v3(route: QueryRoute, evidence: CsmEvidence) -> float:
    if evidence.evidence_type in route.preferred_evidence_types or evidence.observation_type in route.preferred_state_types:
        return 1.0
    if route.mode in EVIDENCE_FIRST_ROUTES or route.mode == "correction_state":
        return 0.70
    if route.mode == "state_first":
        return 0.25
    return 0.45


def recency_score(value: Optional[datetime]) -> float:
    if value is None:
        return 0.35
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (datetime.now(timezone.utc) - value.astimezone(timezone.utc)).total_seconds() / 86400)
    return max(0.05, min(1.0, 1.0 / (1.0 + age_days / 365)))


def serialization_cost_score(token_count: int) -> float:
    return max(0.0, min(1.0, math.log(max(token_count, 1), 1000)))


def is_direct_state_match(route: QueryRoute, state: CsmStateVariable, lexical: float, semantic: float) -> bool:
    return (
        state.state_type in route.preferred_state_types
        or lexical >= 0.16
        or semantic >= 0.35
        or route.mode in {"state_first", "decision_state", "high_risk_review"} and state.state_type in {"condition", "medication", "allergy"}
    )


def compact_state_context_v3(
    *,
    state: CsmStateVariable,
    evidence: Optional[CsmEvidence],
    route: QueryRoute,
    components: dict[str, float],
    historical_value: Optional[dict[str, Any]] = None,
) -> str:
    value = historical_value or state.current_value or {}
    identity = value.get("state_identity") or {}
    display = state_value_display(value)
    support = primary_support_text(evidence, value)
    lines = [
        "[CSM_STATE]",
        f"state: {identity.get('state_type') or state.state_type}",
        f"key: {state.state_key}",
        f"value: {display}",
        f"status: {value.get('status') or state.status}",
        f"valid_time: {value.get('valid_time') or iso(state.valid_from)}",
        f"recorded_time: {value.get('recorded_time') or iso(state.last_updated_at)}",
        f"version: {value.get('transition', {}).get('new_version') or state.current_version}",
        f"confidence: {float(state.confidence or 0):.3f}",
        f"support: {support}",
    ]
    if route.include_historical and historical_value is not None:
        lines.append("history_scope: historical_version")
    if route.mode == "dependency_state":
        lines.append(f"dependency_count: {len(value.get('dependency_ids') or [])}")
    if components:
        lines.append(f"utility: {compact_float_dict(components, limit=6)}")
    lines.append("[/CSM_STATE]")
    return "\n".join(lines)


def compact_evidence_context_v3(
    *,
    evidence: CsmEvidence,
    route: QueryRoute,
    components: dict[str, float],
) -> str:
    lines = [
        "[EVIDENCE]",
        f"evidence_type: {evidence.evidence_type}",
        f"observation_type: {evidence.observation_type or 'unknown'}",
        f"verification: {evidence.verification_status}",
        f"valid_time: {iso(evidence.valid_time)}",
        f"recorded_time: {iso(evidence.recorded_time)}",
        f"source: canonical_source_id={evidence.canonical_source_id}",
    ]
    if evidence.document_id:
        lines.append(f"document: document_id={evidence.document_id} page={evidence.page_number or 'none'} section_id={evidence.section_id or 'none'}")
    lines.append(f"text: {source_preview(evidence.content, max_length=420)}")
    if components:
        lines.append(f"utility: {compact_float_dict(components, limit=6)}")
    lines.append("[/EVIDENCE]")
    return "\n".join(lines)


def state_value_display(value: dict[str, Any]) -> str:
    raw_value = value.get("value")
    if isinstance(raw_value, dict):
        display = raw_value.get("display")
        if display:
            return str(display)
        compact = {key: raw_value.get(key) for key in sorted(raw_value) if raw_value.get(key) is not None}
        return source_preview(str(compact), max_length=220)
    return source_preview(str(raw_value or value.get("raw_value") or "unknown"), max_length=220)


def primary_support_text(evidence: Optional[CsmEvidence], value: dict[str, Any]) -> str:
    if evidence is not None:
        return f"primary evidence {evidence.evidence_type}; canonical_source_id={evidence.canonical_source_id}"
    lineage = value.get("lineage") or {}
    if lineage.get("latest_canonical_source_id"):
        return f"canonical_source_id={lineage['latest_canonical_source_id']}"
    return "support evidence unavailable"


def redundancy_key_for_state(state: CsmStateVariable) -> str:
    value = state.current_value or {}
    status = value.get("status") or state.status
    return f"state:{state.state_type}:{state.state_key}:{status}"


def redundancy_key_for_evidence(evidence: CsmEvidence) -> str:
    normalized = normalize_key(evidence.normalized_value or source_preview(evidence.content, max_length=120))
    return f"evidence:{evidence.source_type}:{evidence.observation_type}:{normalized}:{evidence.valid_time}"


def measurement_display(payload: dict[str, Any], fallback: str) -> str:
    name = payload.get("observation_name") or "measurement"
    value = payload.get("value_numeric") if payload.get("value_numeric") is not None else payload.get("value_text")
    unit = payload.get("unit")
    observed = payload.get("observed_at")
    if value is not None:
        return " ".join(str(part) for part in (name, value, unit, f"at {observed}" if observed else None) if part)
    return source_preview(fallback, max_length=180)


def medication_display(payload: dict[str, Any], fallback: str) -> str:
    parts = [
        payload.get("medication_name"),
        payload.get("generic_name"),
        " ".join(str(value) for value in (payload.get("dosage_value"), payload.get("dosage_unit")) if value),
        payload.get("frequency"),
        payload.get("medication_status"),
    ]
    text = "; ".join(str(part) for part in parts if part)
    return text or source_preview(fallback, max_length=180)


def allergy_display(payload: dict[str, Any], fallback: str) -> str:
    parts = [
        payload.get("substance"),
        payload.get("reaction"),
        payload.get("severity"),
        payload.get("clinical_status"),
        payload.get("verification_status"),
    ]
    text = "; ".join(str(part) for part in parts if part)
    return text or source_preview(fallback, max_length=180)


def condition_display(payload: dict[str, Any], fallback: str) -> str:
    parts = [
        payload.get("name"),
        payload.get("clinical_status"),
        payload.get("verification_status"),
        payload.get("severity"),
    ]
    text = "; ".join(str(part) for part in parts if part)
    return text or source_preview(fallback, max_length=180)


def measurement_numeric_value(value: dict[str, Any]) -> Optional[float]:
    state_value = value.get("value") or {}
    if not isinstance(state_value, dict):
        return None
    numeric = state_value.get("value_numeric")
    if numeric is None:
        structured = value.get("structured") or {}
        numeric = structured.get("value_numeric")
    try:
        return float(numeric)
    except (TypeError, ValueError):
        return None


def measurement_unit(value: dict[str, Any]) -> Optional[str]:
    state_value = value.get("value") or {}
    structured = value.get("structured") or {}
    if isinstance(state_value, dict) and state_value.get("unit"):
        return str(state_value.get("unit"))
    if structured.get("unit"):
        return str(structured.get("unit"))
    return value.get("unit")


def measurement_name_from_state(state: CsmStateVariable) -> str:
    value = state.current_value or {}
    state_value = value.get("value") or {}
    structured = value.get("structured") or {}
    if isinstance(state_value, dict) and state_value.get("observation_name"):
        return str(state_value["observation_name"])
    if structured.get("observation_name"):
        return str(structured["observation_name"])
    return state.state_key.split(":", 1)[-1]


def build_measurement_trend_value(state: CsmStateVariable, histories: list[CsmStateHistory]) -> Optional[dict[str, Any]]:
    values = []
    for history in histories:
        numeric = measurement_numeric_value(history.new_value or {})
        if numeric is None:
            continue
        values.append(
            {
                "numeric": numeric,
                "valid_time": (history.valid_from or parse_iso((history.new_value or {}).get("valid_time"))),
                "recorded_time": history.created_at,
                "value": history.new_value,
            }
        )
    if len(values) < 2:
        return None
    values.sort(key=lambda item: (item["valid_time"] or datetime.min.replace(tzinfo=timezone.utc), item["recorded_time"]))
    previous = values[-2]
    latest = values[-1]
    delta = latest["numeric"] - previous["numeric"]
    direction = "stable"
    if abs(delta) > 0.0001:
        direction = "increasing" if delta > 0 else "decreasing"
    unit = measurement_unit(latest["value"] or state.current_value or {})
    name = measurement_name_from_state(state)
    return {
        "direction": direction,
        "delta": delta,
        "latest_value": latest["numeric"],
        "previous_value": previous["numeric"],
        "unit": unit,
        "latest_valid_time": latest["valid_time"].isoformat() if latest["valid_time"] else None,
        "previous_valid_time": previous["valid_time"].isoformat() if previous["valid_time"] else None,
        "display": f"{name} trend {direction}: {previous['numeric']} -> {latest['numeric']} {unit or ''}".strip(),
    }


def is_renal_measurement_name(name: str) -> bool:
    terms = tokenize(name)
    return bool(terms & RENAL_TERMS)


def build_renal_function_value(state: CsmStateVariable, trend_value: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    name = measurement_name_from_state(state)
    if not is_renal_measurement_name(name):
        return None
    value = state.current_value or {}
    numeric = measurement_numeric_value(value)
    if numeric is None:
        return None
    unit = measurement_unit(value)
    direction = trend_value.get("direction") if trend_value else "single_observation"
    valid_time = value.get("valid_time")
    return {
        "basis": name,
        "latest_measurement": numeric,
        "unit": unit,
        "direction": direction,
        "valid_time": valid_time,
        "display": f"renal function basis {name}: {numeric} {unit or ''}; trend={direction}".strip(),
    }


def tokenize(value: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9]+", (value or "").lower()))


def normalize_key(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text[:180]


def bounded_float(value: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def compact_float_dict(values: dict[str, Any], *, limit: Optional[int] = None) -> str:
    parts = []
    for key, value in values.items():
        if isinstance(value, (int, float)):
            parts.append(f"{key}={float(value):.3f}")
        else:
            parts.append(f"{key}={value}")
        if limit is not None and len(parts) >= limit:
            break
    return ", ".join(parts) if parts else "none"


def parse_iso(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def iso(value: Optional[datetime]) -> str:
    return value.isoformat() if value else "none"
