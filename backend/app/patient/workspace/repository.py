from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.document.models import Document
from app.memory_systems.common.models.memory import MemoryConversation, MemorySystemInstance
from app.patient_information.models import (
    Allergy,
    ClinicalEncounter,
    ClinicalNote,
    Measurement,
    MedicalCondition,
    Medication,
)


INFORMATION_MODELS = {
    "encounters": ClinicalEncounter,
    "conditions": MedicalCondition,
    "medications": Medication,
    "allergies": Allergy,
    "measurements": Measurement,
    "notes": ClinicalNote,
}


def count_patient_information(db: Session, *, patient_id: UUID) -> dict[str, int]:
    counts = {}

    for name, model in INFORMATION_MODELS.items():
        statement = (
            select(func.count())
            .select_from(model)
            .where(
                model.patient_id == patient_id,
                model.is_active.is_(True),
            )
        )
        counts[name] = int(db.scalar(statement) or 0)

    return counts


def count_documents(db: Session, *, patient_id: UUID) -> dict[str, int]:
    counts = {
        "total": 0,
        "pending_upload": 0,
        "uploaded": 0,
        "queued": 0,
        "processing": 0,
        "completed": 0,
        "failed": 0,
        "requires_ocr": 0,
    }
    statement = (
        select(
            Document.upload_status,
            Document.processing_status,
            Document.ocr_requirement_status,
            func.count(),
        )
        .where(
            Document.patient_id == patient_id,
            Document.is_active.is_(True),
        )
        .group_by(
            Document.upload_status,
            Document.processing_status,
            Document.ocr_requirement_status,
        )
    )

    for upload_status, processing_status, ocr_status, row_count in db.execute(statement):
        count = int(row_count or 0)
        counts["total"] += count

        if upload_status in counts:
            counts[upload_status] += count

        if processing_status in counts:
            counts[processing_status] += count

        if ocr_status in {"required", "requires_ocr", "awaiting_ocr"}:
            counts["requires_ocr"] += count

    return counts


def list_memory_system_summaries(db: Session, *, patient_id: UUID) -> list[dict]:
    statement = (
        select(
            MemorySystemInstance.id,
            MemorySystemInstance.system_type,
            MemorySystemInstance.display_name,
            MemorySystemInstance.status,
            MemorySystemInstance.initialized_at,
            MemorySystemInstance.last_synced_at,
            MemorySystemInstance.source_cutoff_time,
            MemorySystemInstance.failure_code,
            MemorySystemInstance.failure_reason,
        )
        .where(MemorySystemInstance.patient_id == patient_id)
        .order_by(MemorySystemInstance.system_type.asc())
    )

    return [dict(row) for row in db.execute(statement).mappings().all()]


def list_recent_conversation_summaries(
    db: Session,
    *,
    doctor_id: UUID,
    patient_id: UUID,
    limit: int = 5,
) -> list[dict]:
    statement = (
        select(
            MemoryConversation.id,
            MemoryConversation.system_type,
            MemoryConversation.title,
            MemoryConversation.status,
            MemoryConversation.updated_at,
            MemoryConversation.last_message_at,
        )
        .where(
            MemoryConversation.doctor_id == doctor_id,
            MemoryConversation.patient_id == patient_id,
        )
        .order_by(MemoryConversation.updated_at.desc(), MemoryConversation.id.desc())
        .limit(limit)
    )

    return [dict(row) for row in db.execute(statement).mappings().all()]
