from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.doctor.model import Doctor
from app.memory_systems.common.models.memory import CanonicalMemorySource
from app.memory_systems.common.schemas.memory import (
    MemoryIngestionRunResponse,
    MemoryRebuildRequest,
    MemorySyncRequest,
)
from app.memory_systems.common.services.memory_service import (
    ensure_instance,
    ensure_owned_patient,
    initialize_missing_system_instances,
    initialize_system,
    rebuild_system,
    sync_system,
)
from app.memory_systems.csm.models import (
    CsmConflict,
    CsmEvidence,
    CsmReviewRequest,
    CsmStateEvidenceLink,
    CsmStateHistory,
    CsmStateVariable,
)
from app.memory_systems.csm.schemas import (
    CsmConflictResponse,
    CsmEvidenceResponse,
    CsmHistoryResponse,
    CsmLineageResponse,
    CsmOverviewResponse,
    CsmReviewResponse,
    CsmStateResponse,
    CsmSummaryResponse,
)
from app.memory_systems.common.registry.registry import registry


def initialize_csm(db: Session, *, doctor: Doctor, patient_id: UUID):
    return initialize_system(db=db, doctor=doctor, patient_id=patient_id, system_type="csm")


def sync_csm(db: Session, *, doctor: Doctor, patient_id: UUID, request: Optional[MemorySyncRequest] = None) -> MemoryIngestionRunResponse:
    return sync_system(
        db=db,
        doctor=doctor,
        patient_id=patient_id,
        system_type="csm",
        request=request
        or MemorySyncRequest(
            include_patient_information=True,
            include_documents=True,
            include_conversation=True,
        ),
    )


def rebuild_csm(db: Session, *, doctor: Doctor, patient_id: UUID, request: Optional[MemoryRebuildRequest] = None) -> MemoryIngestionRunResponse:
    return rebuild_system(
        db=db,
        doctor=doctor,
        patient_id=patient_id,
        system_type="csm",
        request=request
        or MemoryRebuildRequest(
            confirm_rebuild=True,
            include_patient_information=True,
            include_documents=True,
            include_conversation=True,
        ),
    )


def get_csm_overview(db: Session, *, doctor: Doctor, patient_id: UUID) -> CsmOverviewResponse:
    ensure_owned_patient(db=db, doctor=doctor, patient_id=patient_id)
    initialize_missing_system_instances(db=db, patient_id=patient_id)
    instance = ensure_instance(db=db, patient_id=patient_id, system_type="csm")

    states = list(
        db.scalars(
            select(CsmStateVariable)
            .where(CsmStateVariable.system_instance_id == instance.id)
            .order_by(CsmStateVariable.last_updated_at.desc(), CsmStateVariable.created_at.desc())
        ).all()
    )
    evidence = list(
        db.scalars(
            select(CsmEvidence)
            .where(CsmEvidence.system_instance_id == instance.id)
            .order_by(CsmEvidence.created_at.desc())
        ).all()
    )
    links = list(
        db.execute(
            select(CsmStateEvidenceLink, CsmStateVariable)
            .join(CsmStateVariable, CsmStateEvidenceLink.state_variable_id == CsmStateVariable.id)
            .where(CsmStateVariable.system_instance_id == instance.id)
        ).all()
    )
    histories = list(
        db.execute(
            select(CsmStateHistory, CsmStateVariable)
            .join(CsmStateVariable, CsmStateHistory.state_variable_id == CsmStateVariable.id)
            .where(CsmStateVariable.system_instance_id == instance.id)
            .order_by(CsmStateHistory.created_at.desc())
        ).all()
    )
    conflicts = list(
        db.scalars(
            select(CsmConflict)
            .where(CsmConflict.system_instance_id == instance.id)
            .order_by(CsmConflict.created_at.desc())
        ).all()
    )
    reviews = list(
        db.scalars(
            select(CsmReviewRequest)
            .where(CsmReviewRequest.system_instance_id == instance.id)
            .order_by(CsmReviewRequest.created_at.desc())
        ).all()
    )

    pending_reviews_by_source = {
        review.canonical_source_id: review
        for review in reviews
        if review.status == "pending"
    }
    evidence_to_state = {link.evidence_id: state.id for link, state in links}
    state_evidence = {}
    for link, _state in links:
        state_evidence.setdefault(link.state_variable_id, []).append(link.evidence_id)

    state_responses = [
        serialize_state(state, evidence_ids=state_evidence.get(state.id, []))
        for state in states
    ]
    review_evidence_ids = {}
    for item in evidence:
        review = pending_reviews_by_source.get(item.canonical_source_id)
        if review:
            evidence_to_state[item.id] = review.id
            review_evidence_ids.setdefault(review.id, []).append(item.id)

    state_responses.extend(
        serialize_review_as_state(review, evidence_ids=review_evidence_ids.get(review.id, []))
        for review in reviews
        if review.status == "pending"
    )

    evidence_responses = [
        serialize_evidence(
            item,
            state_id=evidence_to_state.get(item.id),
            review_id=pending_reviews_by_source.get(item.canonical_source_id).id
            if item.canonical_source_id in pending_reviews_by_source
            else None,
        )
        for item in evidence
    ]
    history_responses = [serialize_history(history, state) for history, state in histories]
    lineage = [
        CsmLineageResponse(
            type="State Version",
            identifier=str(history.id),
            timestamp=format_dt(history.created_at),
            actor="CSM update engine",
            version=f"v{history.version_number}",
            summary=f"{state.state_key}: {display_value(history.new_value)}",
        )
        for history, state in histories[:20]
    ]

    summary = CsmSummaryResponse(
        availability="CSM Ready" if state_responses else "CSM Not Initialized",
        state_version=sum(state.current_version for state in states),
        sync_status=instance.status,
        last_state_update=format_dt(max((state.last_updated_at for state in states), default=None)),
        total_active_states=sum(1 for state in states if state.status == "active"),
        contested_states=sum(1 for state in states if state.status == "contested"),
        pending_review_states=sum(1 for review in reviews if review.status == "pending"),
        evidence_count=len(evidence),
        conflict_count=len(conflicts),
        review_count=len(reviews),
    )

    return CsmOverviewResponse(
        summary=summary,
        states=state_responses,
        evidence=evidence_responses,
        history=history_responses,
        lineage=lineage,
        conflicts=[serialize_conflict(conflict) for conflict in conflicts],
        reviews=[serialize_review(review) for review in reviews],
    )


def get_csm_evidence(db: Session, *, doctor: Doctor, patient_id: UUID) -> list[CsmEvidenceResponse]:
    return get_csm_overview(db=db, doctor=doctor, patient_id=patient_id).evidence


def get_csm_evidence_item(
    db: Session,
    *,
    doctor: Doctor,
    patient_id: UUID,
    evidence_id: UUID,
) -> CsmEvidenceResponse:
    for evidence in get_csm_evidence(db=db, doctor=doctor, patient_id=patient_id):
        if evidence.id == evidence_id:
            return evidence

    raise ValueError("CSM evidence record not found.")


def approve_review(db: Session, *, doctor: Doctor, patient_id: UUID, review_id: UUID, note: Optional[str]) -> CsmReviewResponse:
    ensure_owned_patient(db=db, doctor=doctor, patient_id=patient_id)
    instance = ensure_instance(db=db, patient_id=patient_id, system_type="csm")
    review = get_review(db, instance_id=instance.id, review_id=review_id)
    source = db.get(CanonicalMemorySource, review.canonical_source_id)
    evidence = db.scalar(
        select(CsmEvidence).where(
            CsmEvidence.system_instance_id == instance.id,
            CsmEvidence.canonical_source_id == review.canonical_source_id,
        )
    )

    if source is None or evidence is None:
        raise ValueError("Review source or evidence was not found.")

    evidence.verification_status = "verified"
    evidence.confidence = max(evidence.confidence, 0.85)
    adapter = registry.get("csm")
    state = adapter.upsert_state_from_evidence(db=db, instance=instance, source=source, evidence=evidence)
    state.status = "active"
    state.update_operator = "conversation_approved_doctor_review"
    state.uncertainty = {
        "extraction_confidence": 0.7,
        "source_reliability": 0.9,
        "posterior_uncertainty": 0.15,
        "epistemic_uncertainty": 0.1,
    }
    review.status = "approved"
    review.reviewed_by = doctor.id
    review.reviewed_at = utc_now()
    review.review_note = note
    db.commit()
    db.refresh(review)
    return serialize_review(review)


def reject_review(db: Session, *, doctor: Doctor, patient_id: UUID, review_id: UUID, note: Optional[str]) -> CsmReviewResponse:
    ensure_owned_patient(db=db, doctor=doctor, patient_id=patient_id)
    instance = ensure_instance(db=db, patient_id=patient_id, system_type="csm")
    review = get_review(db, instance_id=instance.id, review_id=review_id)
    review.status = "rejected"
    review.reviewed_by = doctor.id
    review.reviewed_at = utc_now()
    review.review_note = note
    db.commit()
    db.refresh(review)
    return serialize_review(review)


def get_review(db: Session, *, instance_id: UUID, review_id: UUID) -> CsmReviewRequest:
    review = db.scalar(
        select(CsmReviewRequest).where(
            CsmReviewRequest.id == review_id,
            CsmReviewRequest.system_instance_id == instance_id,
        )
    )

    if review is None:
        raise ValueError("CSM review request not found.")

    return review


def serialize_state(state: CsmStateVariable, *, evidence_ids: list[UUID]) -> CsmStateResponse:
    current_value = state.current_value or {}
    uncertainty = state.uncertainty or {}
    return CsmStateResponse(
        id=state.id,
        name=state_display_name(state),
        category=category_for_state(state),
        display_value=display_value(current_value),
        unit=str(current_value.get("structured", {}).get("unit") or current_value.get("structured", {}).get("dosage_unit") or ""),
        status=title_status(state.status),
        support_status=support_status_for_state(state),
        state_version=state.current_version,
        effective_from=format_dt(state.valid_from),
        effective_until=format_dt(state.valid_to) if state.valid_to else "Not applicable",
        last_observed_at=format_dt(state.valid_from),
        updated_at=format_dt(state.last_updated_at),
        next_review_date="Not scheduled",
        trend="Stable",
        uncertainty_summary=uncertainty_summary(uncertainty),
        source_count=len(evidence_ids),
        active_evidence_count=len(evidence_ids),
        conflicting_evidence_ids=[],
        pending_evidence_count=1 if state.status in {"candidate", "pending_review"} else 0,
        evidence_ids=evidence_ids,
        upstream_dependency_ids=[],
        downstream_dependency_ids=[],
        activated=False,
        stale=False,
        update_operator=state.update_operator,
        status_reason=str(current_value.get("source_type", "evidence-derived")),
    )


def serialize_review_as_state(review: CsmReviewRequest, *, evidence_ids: list[UUID]) -> CsmStateResponse:
    return CsmStateResponse(
        id=review.id,
        name=f"Review: {review.proposed_state_type.replace('_', ' ')}",
        category="Symptom",
        display_value=display_value(review.proposed_value),
        status="Pending Review",
        support_status="Insufficient Evidence",
        state_version=1,
        effective_from=format_dt(review.created_at),
        effective_until="Not applicable",
        last_observed_at=format_dt(review.created_at),
        updated_at=format_dt(review.updated_at),
        next_review_date="Doctor approval required",
        trend="Conversation proposal",
        uncertainty_summary="Conversation-derived state proposals are stored for review and do not update permanent state until approved.",
        source_count=1,
        active_evidence_count=0,
        pending_evidence_count=1,
        evidence_ids=evidence_ids,
        update_operator="conversation_review_gate",
        status_reason=review.support_status,
        review_id=review.id,
    )


def serialize_evidence(
    evidence: CsmEvidence,
    *,
    state_id: Optional[UUID],
    review_id: Optional[UUID],
) -> CsmEvidenceResponse:
    return CsmEvidenceResponse(
        id=evidence.id,
        state_id=state_id,
        review_id=review_id,
        canonical_source_id=evidence.canonical_source_id,
        group="Pending Review" if evidence.verification_status == "pending_review" else "Supporting Evidence",
        source_title=evidence.normalized_value or evidence.observation_type or evidence.evidence_type,
        source_type=title_status(evidence.source_type),
        effective_date=format_dt(evidence.valid_time),
        excerpt=evidence.content,
        evidence_status="ActiveEvidence" if evidence.is_active else "Retracted",
        verification=title_status(evidence.verification_status),
        contribution=evidence.evidence_type,
        document_id=evidence.document_id,
        page_number=evidence.page_number,
        section_id=evidence.section_id,
        conversation_id=evidence.conversation_id,
        message_id=evidence.message_id,
    )


def serialize_history(history: CsmStateHistory, state: CsmStateVariable) -> CsmHistoryResponse:
    return CsmHistoryResponse(
        id=history.id,
        state_id=state.id,
        effective_at=format_dt(history.created_at),
        previous_value=display_value(history.previous_value),
        new_value=display_value(history.new_value),
        reason=history.update_reason,
        state_version=history.version_number,
    )


def serialize_conflict(conflict: CsmConflict) -> CsmConflictResponse:
    return CsmConflictResponse(
        id=conflict.id,
        state_id=conflict.state_variable_id,
        evidence_a_id=conflict.evidence_a_id,
        evidence_b_id=conflict.evidence_b_id,
        conflict_type=conflict.conflict_type,
        status=conflict.status,
        resolution=conflict.resolution,
        created_at=format_dt(conflict.created_at),
    )


def serialize_review(review: CsmReviewRequest) -> CsmReviewResponse:
    return CsmReviewResponse(
        id=review.id,
        proposed_claim=review.proposed_claim,
        proposed_state_type=review.proposed_state_type,
        proposed_value=review.proposed_value,
        support_status=review.support_status,
        risk_level=review.risk_level,
        status=review.status,
        created_at=format_dt(review.created_at),
        reviewed_at=format_dt(review.reviewed_at) if review.reviewed_at else None,
        review_note=review.review_note,
    )


def state_display_name(state: CsmStateVariable) -> str:
    structured = (state.current_value or {}).get("structured") or {}
    for key in ("name", "medication_name", "substance", "observation_name", "title", "original_filename"):
        if structured.get(key):
            return str(structured[key])

    return state.state_key.replace(":", " ").replace("_", " ").title()


def display_value(value: Optional[dict]) -> str:
    if not value:
        return "Not recorded"

    structured = value.get("structured") or {}
    for key in ("clinical_status", "medication_status", "reaction", "value_text", "status", "document_type"):
        if structured.get(key):
            return str(structured[key]).replace("_", " ").title()

    if structured.get("value_numeric") is not None:
        unit = structured.get("unit") or ""
        return f"{structured['value_numeric']} {unit}".strip()

    content = str(value.get("content") or "")
    return content[:120] + ("..." if len(content) > 120 else "")


def category_for_state(state: CsmStateVariable) -> str:
    mapping = {
        "condition": "Diagnosis",
        "medication": "Medication",
        "allergy": "Allergy",
        "measurement": "Vital Sign",
        "encounter": "Treatment",
        "clinical_note": "Symptom",
        "document": "Treatment",
        "section": "Treatment",
        "page": "Treatment",
        "extracted_text": "Treatment",
    }
    return mapping.get(state.state_type, "Symptom")


def support_status_for_state(state: CsmStateVariable) -> str:
    if state.status == "active":
        return "Supported"

    if state.status == "candidate":
        return "Partially Supported"

    if state.status == "contested":
        return "Conflicting Evidence"

    return "Insufficient Evidence"


def uncertainty_summary(uncertainty: dict) -> str:
    if not uncertainty:
        return "No uncertainty details recorded."

    return (
        f"Extraction confidence {uncertainty.get('extraction_confidence', 'n/a')}; "
        f"source reliability {uncertainty.get('source_reliability', 'n/a')}; "
        f"epistemic uncertainty {uncertainty.get('epistemic_uncertainty', 'n/a')}."
    )


def title_status(value: str) -> str:
    return str(value or "").replace("_", " ").title()


def format_dt(value: Optional[datetime]) -> str:
    if value is None:
        return "Not recorded"
    return value.isoformat()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
