from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from app.memory_systems.common.registry.adapter import source_preview
from app.memory_systems.common.token_budget.service import estimate_tokens
from app.memory_systems.csm.models import CsmEvidence, CsmStateVariable


CSM_V2_IMPLEMENTATION_VERSION = "csm_v2"
CSM_V2_STATE_SCHEMA_VERSION = "csm_state_schema_v2"

ROUTER_MODES = {
    "state_first",
    "temporal_state",
    "correction_state",
    "dependency_state",
    "decision_state",
    "evidence_first",
    "exact_source",
    "rare_detail",
    "hybrid_state_evidence",
    "high_risk_review",
}

PATIENT_INFO_STATE_TYPES = {
    "condition": "clinical_condition",
    "medication": "medication",
    "allergy": "allergy",
    "measurement": "measurement",
    "encounter": "clinical_encounter",
    "clinical_note": "clinical_note",
}

HIGH_RISK_TERMS = {
    "allergy",
    "allergic",
    "anaphylaxis",
    "medication",
    "dose",
    "dosage",
    "discontinue",
    "stop",
    "urgent",
    "emergency",
    "adverse",
    "contraindication",
    "contraindicated",
    "diagnosis",
    "treatment",
}

TEMPORAL_TERMS = {
    "after",
    "before",
    "current",
    "currently",
    "latest",
    "now",
    "previous",
    "prior",
    "trend",
    "timeline",
    "when",
}

CORRECTION_TERMS = {
    "addendum",
    "amended",
    "corrected",
    "correction",
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
    "report",
    "result",
    "record",
    "document",
}


@dataclass(frozen=True)
class QueryRoute:
    mode: str
    features: dict[str, Any]
    reason: str
    fallback_strategy: str
    preferred_state_types: tuple[str, ...]
    preferred_evidence_types: tuple[str, ...]


@dataclass(frozen=True)
class ActivationCandidate:
    kind: str
    state: Optional[CsmStateVariable]
    evidence: Optional[CsmEvidence]
    score: float
    components: dict[str, float]
    reason: str
    token_count: int


def route_query(query: str) -> QueryRoute:
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
        "has_number": has_number,
        "has_date": has_date,
        "token_count": len(terms),
    }

    if features["high_risk_terms"] and (features["decision_terms"] or "should" in terms):
        mode = "high_risk_review"
        reason = "high_risk_decision_terms"
    elif features["correction_terms"]:
        mode = "correction_state"
        reason = "correction_or_supersession_terms"
    elif features["dependency_terms"]:
        mode = "dependency_state"
        reason = "dependency_or_propagation_terms"
    elif features["temporal_terms"] or has_date:
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
        reason = "default_state_lookup"

    return QueryRoute(
        mode=mode,
        features=features,
        reason=reason,
        fallback_strategy="raw_evidence_when_state_confidence_or_relevance_is_low",
        preferred_state_types=preferred_state_types(terms, mode),
        preferred_evidence_types=preferred_evidence_types(terms, mode),
    )


def preferred_state_types(terms: set[str], mode: str) -> tuple[str, ...]:
    selected: list[str] = []
    if {"condition", "conditions", "diagnosis", "diagnoses"} & terms:
        selected.append("condition")
    if {"medication", "medications", "drug", "dose", "dosage"} & terms:
        selected.append("medication")
    if {"allergy", "allergies", "reaction"} & terms:
        selected.append("allergy")
    if {"lab", "labs", "measurement", "value", "result", "egfr", "creatinine"} & terms:
        selected.append("measurement")
    if {"note", "notes"} & terms:
        selected.append("clinical_note")
    if {"document", "report", "page", "source", "evidence", "citation"} & terms:
        selected.extend(["document", "section", "page", "extracted_text"])
    if mode in {"temporal_state", "correction_state", "dependency_state", "hybrid_state_evidence"}:
        selected.extend(["measurement", "clinical_note", "document", "section", "page", "extracted_text"])
    return tuple(dict.fromkeys(selected))


def preferred_evidence_types(terms: set[str], mode: str) -> tuple[str, ...]:
    selected: list[str] = []
    if {"document", "report", "page", "source", "evidence", "citation", "quote"} & terms:
        selected.extend(["document_candidate_material", "structured_clinical_note", "structured_measurement"])
    if {"lab", "labs", "measurement", "result", "value", "creatinine", "egfr"} & terms:
        selected.extend(["structured_measurement", "document_candidate_material"])
    if mode in {"evidence_first", "exact_source", "correction_state", "rare_detail"}:
        selected.extend(["document_candidate_material", "structured_measurement", "structured_clinical_note"])
    return tuple(dict.fromkeys(selected))


def build_state_value_payload(
    *,
    source,
    evidence: CsmEvidence,
    operation: str,
    version: int,
    previous_value: Optional[dict[str, Any]],
    supersedes: list[str],
    dependency_ids: list[str],
) -> dict[str, Any]:
    structured = dict(source.structured_payload or {})
    semantic_type = semantic_state_type(source)
    value = normalized_value_for_payload(source)
    status = state_lifecycle_status(source)
    now = datetime.now(timezone.utc).isoformat()
    previous_evidence_ids = set(previous_value.get("evidence_ids") or []) if previous_value else set()
    previous_source_ids = set(previous_value.get("recorded_source_ids") or []) if previous_value else set()
    evidence_ids = sorted(previous_evidence_ids | {str(evidence.id)})
    source_ids = sorted(previous_source_ids | {str(source.id)})

    return {
        "schema_version": CSM_V2_STATE_SCHEMA_VERSION,
        "implementation_version": CSM_V2_IMPLEMENTATION_VERSION,
        "state_identity": {
            "semantic_type": semantic_type,
            "source_subtype": source.source_subtype,
            "state_key": state_key_for_source_v2(source),
            "normalized_value": normalized_key_value(source),
        },
        "value": value,
        "raw_value": source.content_text,
        "structured": structured,
        "unit": structured.get("unit") or structured.get("dosage_unit"),
        "status": status,
        "valid_time": source.valid_time.isoformat() if source.valid_time else None,
        "recorded_time": source.recorded_time.isoformat() if source.recorded_time else None,
        "event_time": source.event_time.isoformat() if getattr(source, "event_time", None) else None,
        "recorded_source_ids": source_ids,
        "evidence_ids": evidence_ids,
        "lineage": {
            "latest_canonical_source_id": str(source.id),
            "latest_evidence_id": str(evidence.id),
            "document_id": str(source.document_id) if source.document_id else None,
            "page_number": source.page_number,
            "section_id": str(source.section_id) if source.section_id else None,
            "source_hash": source.content_hash,
            "source_type": source.source_type,
            "source_subtype": source.source_subtype,
        },
        "confidence_components": {
            "source_confidence": float(evidence.confidence),
            "verification_weight": verification_weight(evidence.verification_status),
            "structure_weight": 1.0 if structured else 0.65,
        },
        "uncertainty_components": uncertainty_components(source, evidence),
        "supersedes": sorted(set(supersedes)),
        "superseded_by": [],
        "dependency_ids": sorted(set(dependency_ids)),
        "change_operation": operation,
        "version": version,
        "audit": {
            "updated_at": now,
            "update_operator": "deterministic_csm_v2_state_upsert",
            "requires_review": evidence.verification_status == "pending_review",
            "risk_level": risk_level_text(f"{source.source_subtype} {source.content_text}"),
        },
    }


def update_previous_supersession(previous_value: Optional[dict[str, Any]], *, evidence_id: str) -> Optional[dict[str, Any]]:
    if not previous_value:
        return previous_value

    updated = dict(previous_value)
    superseded_by = set(updated.get("superseded_by") or [])
    superseded_by.add(evidence_id)
    updated["superseded_by"] = sorted(superseded_by)
    updated["status"] = "superseded"
    return updated


def semantic_state_type(source) -> str:
    if source.source_type == "patient_information":
        return PATIENT_INFO_STATE_TYPES.get(source.source_subtype, source.source_subtype)
    if source.source_type == "document":
        return "document_evidence"
    if source.source_type == "conversation":
        return "conversation_claim"
    return source.source_subtype


def state_lifecycle_status(source) -> str:
    payload = source.structured_payload or {}
    for key in ("clinical_status", "medication_status", "status", "verification_status"):
        value = payload.get(key)
        if value:
            text = str(value).lower()
            if text in {"inactive", "stopped", "resolved", "entered-in-error", "cancelled", "completed"}:
                return "inactive"
            if text in {"active", "confirmed", "final", "available"}:
                return "active"
    if payload.get("end_date") or payload.get("resolved_date"):
        return "inactive"
    return "active" if source.source_type == "patient_information" else "candidate"


def normalized_value_for_payload(source) -> str:
    payload = source.structured_payload or {}
    value_fields = (
        "name",
        "medication_name",
        "substance",
        "observation_name",
        "encounter_type",
        "title",
        "original_filename",
        "document_type",
    )
    for key in value_fields:
        value = payload.get(key)
        if value:
            return str(value)
    if payload.get("value_numeric") is not None:
        unit = payload.get("unit")
        return f"{payload.get('observation_name') or 'measurement'}={payload['value_numeric']}{unit or ''}"
    if payload.get("value_text"):
        return str(payload["value_text"])
    return source_preview(source.content_text, max_length=180)


def normalized_key_value(source) -> str:
    return normalize_key(normalized_value_for_payload(source))


def state_key_for_source_v2(source) -> str:
    semantic = semantic_state_type(source)
    key_value = normalized_key_value(source)
    if key_value:
        return f"{semantic}:{key_value}"
    return f"{semantic}:{source.source_record_id}"


def state_status_for_source_v2(source) -> str:
    if source.source_type == "patient_information":
        return "active"
    if source.source_type == "document":
        return "candidate"
    return "pending_review"


def update_operator_for_source_v2(source) -> str:
    if source.source_type == "patient_information":
        return "deterministic_csm_v2_structured_state_upsert"
    if source.source_type == "document":
        return "deterministic_csm_v2_document_candidate_upsert"
    return "deterministic_csm_v2_conversation_review"


def update_reason_for_source_v2(source, operation: str) -> str:
    if operation == "supersede":
        return "generic_same_key_source_version_supersession"
    if source.source_type == "patient_information":
        return "structured_patient_information_committed_v2"
    if source.source_type == "document":
        return "document_candidate_evidence_ingested_v2"
    return "conversation_proposal_requires_review_v2"


def uncertainty_components(source, evidence: CsmEvidence) -> dict[str, float]:
    base = 1.0 - max(0.0, min(1.0, float(evidence.confidence)))
    candidate_penalty = 0.15 if source.source_type == "document" else 0.0
    review_penalty = 0.35 if source.source_type == "conversation" else 0.0
    return {
        "posterior_uncertainty": min(1.0, base + candidate_penalty + review_penalty),
        "source_reliability_uncertainty": 1.0 - verification_weight(evidence.verification_status),
        "temporal_uncertainty": 0.15 if source.valid_time is None else 0.03,
    }


def verification_weight(status: str) -> float:
    return {
        "verified": 1.0,
        "candidate": 0.72,
        "pending_review": 0.35,
    }.get(status, 0.5)


def should_supersede(previous_value: Optional[dict[str, Any]], source, evidence: CsmEvidence) -> bool:
    if not previous_value:
        return False
    lineage = previous_value.get("lineage") or {}
    if lineage.get("source_hash") == source.content_hash:
        return False
    previous_recorded = parse_iso(previous_value.get("recorded_time"))
    current_recorded = source.recorded_time
    if previous_recorded and current_recorded and current_recorded < previous_recorded:
        return False
    return True


def score_state(
    *,
    query_terms: set[str],
    route: QueryRoute,
    state: CsmStateVariable,
    evidence: Optional[CsmEvidence],
    dependency_score: float,
) -> tuple[float, dict[str, float], str]:
    state_text = f"{state.state_key} {state.state_type} {state.current_value}"
    state_terms = tokenize(state_text)
    relevance = lexical_overlap(query_terms, state_terms)
    route_bonus = route_state_bonus(route, state)
    evidence_score = verification_weight(evidence.verification_status) if evidence else 0.45
    confidence = max(0.0, min(1.0, float(state.confidence or 0.0)))
    recency = recency_component(state.last_updated_at)
    status_weight = 1.0 if state.status == "active" else 0.78 if state.status == "candidate" else 0.35
    utility = (
        relevance * 0.42
        + confidence * 0.18
        + evidence_score * 0.14
        + dependency_score * 0.10
        + route_bonus * 0.10
        + recency * 0.06
    ) * status_weight
    reason = "selected_state_%s" % route.mode if utility >= 0.12 else "low_utility_state_%s" % route.mode
    return utility, {
        "relevance": relevance,
        "confidence": confidence,
        "evidence": evidence_score,
        "dependency": dependency_score,
        "route": route_bonus,
        "recency": recency,
        "status_weight": status_weight,
    }, reason


def score_evidence(*, query_terms: set[str], route: QueryRoute, evidence: CsmEvidence) -> tuple[float, dict[str, float], str]:
    evidence_terms = tokenize(f"{evidence.observation_type} {evidence.evidence_type} {evidence.normalized_value or ''} {evidence.content}")
    relevance = lexical_overlap(query_terms, evidence_terms)
    route_bonus = route_evidence_bonus(route, evidence)
    confidence = max(0.0, min(1.0, float(evidence.confidence or 0.0)))
    verification = verification_weight(evidence.verification_status)
    recency = recency_component(evidence.recorded_time)
    status_weight = 1.0 if evidence.is_active else 0.0
    utility = (
        relevance * 0.46
        + confidence * 0.16
        + verification * 0.18
        + route_bonus * 0.14
        + recency * 0.06
    ) * status_weight
    reason = "selected_evidence_%s" % route.mode if utility >= 0.10 else "low_utility_evidence_%s" % route.mode
    return utility, {
        "relevance": relevance,
        "confidence": confidence,
        "verification": verification,
        "route": route_bonus,
        "recency": recency,
        "status_weight": status_weight,
    }, reason


def route_state_bonus(route: QueryRoute, state: CsmStateVariable) -> float:
    if state.state_type in route.preferred_state_types:
        return 1.0
    semantic = (state.current_value or {}).get("state_identity", {}).get("semantic_type")
    if semantic in route.preferred_state_types:
        return 1.0
    if route.mode in {"state_first", "temporal_state", "dependency_state", "correction_state"}:
        return 0.55
    if route.mode in {"exact_source", "evidence_first"}:
        return 0.25
    return 0.4


def route_evidence_bonus(route: QueryRoute, evidence: CsmEvidence) -> float:
    if evidence.evidence_type in route.preferred_evidence_types or evidence.observation_type in route.preferred_state_types:
        return 1.0
    if route.mode in {"exact_source", "evidence_first", "rare_detail", "correction_state"}:
        return 0.65
    if route.mode == "state_first":
        return 0.25
    return 0.45


def dependency_score_for_state(state: CsmStateVariable, dependency_counts: dict[str, int]) -> float:
    count = dependency_counts.get(str(state.id), 0)
    return min(1.0, count / 3)


def compact_state_context(
    *,
    state: CsmStateVariable,
    evidence: Optional[CsmEvidence],
    route: QueryRoute,
    components: dict[str, float],
) -> str:
    value = state.current_value or {}
    identity = value.get("state_identity") or {}
    lineage = value.get("lineage") or {}
    uncertainty = value.get("uncertainty_components") or {}
    evidence_excerpt = source_preview(evidence.content if evidence else value.get("raw_value", ""), max_length=360)
    lines = [
        "CSM_STATE",
        f"route_mode: {route.mode}",
        f"state_key: {state.state_key}",
        f"semantic_type: {identity.get('semantic_type') or state.state_type}",
        f"value: {value.get('value') or source_preview(str(value.get('raw_value') or ''), 160)}",
        f"status: {value.get('status') or state.status}",
        f"valid_time: {value.get('valid_time') or iso(state.valid_from)}",
        f"recorded_time: {value.get('recorded_time') or iso(state.last_updated_at)}",
        f"confidence: {state.confidence:.3f}",
        f"uncertainty: {compact_float_dict(uncertainty, limit=2)}",
        f"version: {state.current_version}",
        f"canonical_source_id: {lineage.get('latest_canonical_source_id') or (str(evidence.canonical_source_id) if evidence else 'none')}",
        f"document_id: {lineage.get('document_id') or (str(evidence.document_id) if evidence and evidence.document_id else 'none')}",
        f"page_number: {lineage.get('page_number') if lineage.get('page_number') is not None else (evidence.page_number if evidence else 'none')}",
        f"section_id: {lineage.get('section_id') or (str(evidence.section_id) if evidence and evidence.section_id else 'none')}",
        f"supersedes_count: {len(value.get('supersedes') or [])}",
        f"dependency_count: {len(value.get('dependency_ids') or [])}",
        f"activation_components: {compact_float_dict(components, limit=4)}",
        f"evidence_excerpt: {evidence_excerpt}",
    ]
    return "\n".join(lines)


def compact_evidence_context(*, evidence: CsmEvidence, route: QueryRoute, components: dict[str, float]) -> str:
    lines = [
        "CSM_RAW_EVIDENCE",
        f"route_mode: {route.mode}",
        f"evidence_type: {evidence.evidence_type}",
        f"observation_type: {evidence.observation_type}",
        f"verification_status: {evidence.verification_status}",
        f"valid_time: {iso(evidence.valid_time)}",
        f"recorded_time: {iso(evidence.recorded_time)}",
        f"canonical_source_id: {evidence.canonical_source_id}",
        f"document_id: {evidence.document_id or 'none'}",
        f"page_number: {evidence.page_number or 'none'}",
        f"section_id: {evidence.section_id or 'none'}",
        f"confidence: {evidence.confidence:.3f}",
        f"activation_components: {compact_float_dict(components, limit=4)}",
        f"content: {source_preview(evidence.content, max_length=420)}",
    ]
    return "\n".join(lines)


def evidence_token_count(evidence: CsmEvidence) -> int:
    return estimate_tokens(compact_evidence_context(evidence=evidence, route=route_query(""), components={}))


def tokenize(value: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9]+", (value or "").lower()))


def lexical_overlap(query_terms: set[str], candidate_terms: set[str]) -> float:
    if not query_terms or not candidate_terms:
        return 0.0
    expanded_query = expand_terms(query_terms)
    return len(expanded_query & candidate_terms) / max(1, len(expanded_query))


def expand_terms(terms: set[str]) -> set[str]:
    expanded = set(terms)
    synonyms = {
        "kidney": {"renal", "creatinine", "egfr"},
        "renal": {"kidney", "creatinine", "egfr"},
        "lab": {"measurement", "result", "report"},
        "labs": {"measurement", "result", "report"},
        "medicine": {"medication", "drug"},
        "medications": {"medication", "drug"},
        "followup": {"follow", "up", "follow-up"},
        "source": {"evidence", "document", "citation"},
    }
    for term in list(terms):
        expanded.update(synonyms.get(term, set()))
    return expanded


def recency_component(value: Optional[datetime]) -> float:
    if value is None:
        return 0.25
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (datetime.now(timezone.utc) - value.astimezone(timezone.utc)).total_seconds() / 86400)
    return max(0.05, min(1.0, 1.0 / (1.0 + age_days / 365)))


def compact_float_dict(values: dict[str, Any], *, limit: Optional[int] = None) -> str:
    parts = []
    for key, value in sorted(values.items()):
        if isinstance(value, (int, float)):
            parts.append(f"{key}={float(value):.3f}")
        else:
            parts.append(f"{key}={value}")
        if limit is not None and len(parts) >= limit:
            break
    return ", ".join(parts) if parts else "none"


def risk_level_text(text: str) -> str:
    terms = tokenize(text)
    return "high" if terms & HIGH_RISK_TERMS else "medium"


def normalize_key(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text[:180]


def parse_iso(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def iso(value: Optional[datetime]) -> str:
    return value.isoformat() if value else "none"
