from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.document.models import Document, DocumentPage, DocumentSection, DocumentText
from app.memory_systems.common.canonical.serializers import (
    serialize_conversation_message,
    serialize_document_metadata,
    serialize_document_page,
    serialize_document_section,
    serialize_document_text,
    serialize_patient_record,
)
from app.memory_systems.common.models.memory import MemoryConversation, MemoryMessage, MemorySystemInstance
from app.memory_systems.common.schemas.canonical import CanonicalSourceInput
from app.patient_information.models import (
    Allergy,
    ClinicalEncounter,
    ClinicalNote,
    Measurement,
    MedicalCondition,
    Medication,
)


def collect_sources(
    db: Session,
    *,
    patient_id: UUID,
    instance: MemorySystemInstance,
    cutoff_time: datetime,
    include_patient_information: bool,
    include_documents: bool,
    include_conversation: bool,
) -> list[CanonicalSourceInput]:
    sources: list[CanonicalSourceInput] = []

    if include_patient_information:
        sources.extend(
            collect_patient_information_sources(
                db=db,
                patient_id=patient_id,
                cutoff_time=cutoff_time,
            )
        )

    if include_documents:
        sources.extend(
            collect_document_sources(
                db=db,
                patient_id=patient_id,
                cutoff_time=cutoff_time,
            )
        )

    if include_conversation:
        sources.extend(
            collect_conversation_sources(
                db=db,
                patient_id=patient_id,
                instance=instance,
                cutoff_time=cutoff_time,
            )
        )

    return sources


def collect_patient_information_sources(
    db: Session,
    *,
    patient_id: UUID,
    cutoff_time: datetime,
) -> list[CanonicalSourceInput]:
    model_pairs = (
        (ClinicalEncounter, "encounter"),
        (MedicalCondition, "condition"),
        (Medication, "medication"),
        (Allergy, "allergy"),
        (Measurement, "measurement"),
        (ClinicalNote, "clinical_note"),
    )
    sources: list[CanonicalSourceInput] = []

    for model, subtype in model_pairs:
        statement = select(model).where(
            model.patient_id == patient_id,
            model.is_active.is_(True),
            model.created_at <= cutoff_time,
        )
        records = list(db.scalars(statement).all())
        sources.extend(
            serialize_patient_record(
                record,
                patient_id=patient_id,
                subtype=subtype,
            )
            for record in records
        )

    return sources


def collect_document_sources(
    db: Session,
    *,
    patient_id: UUID,
    cutoff_time: datetime,
) -> list[CanonicalSourceInput]:
    statement = (
        select(Document)
        .where(
            Document.patient_id == patient_id,
            Document.is_active.is_(True),
            Document.upload_status == "uploaded",
            Document.created_at <= cutoff_time,
        )
        .order_by(Document.created_at.asc())
    )
    documents = list(db.scalars(statement).all())
    sources: list[CanonicalSourceInput] = []

    for document in documents:
        sources.append(serialize_document_metadata(document))

        if document.text_extraction_status in {"awaiting_ocr", "no_text_found"}:
            continue

        sections = list(
            db.scalars(
                select(DocumentSection)
                .where(DocumentSection.document_id == document.id)
                .order_by(DocumentSection.section_index.asc())
            ).all()
        )

        if sections:
            sources.extend(
                serialize_document_section(section, document=document)
                for section in sections
                if section.normalized_text
            )
            continue

        pages = list(
            db.scalars(
                select(DocumentPage)
                .where(DocumentPage.document_id == document.id)
                .order_by(DocumentPage.page_number.asc())
            ).all()
        )

        if pages:
            sources.extend(
                serialize_document_page(page, document=document)
                for page in pages
                if page.normalized_text
            )
            continue

        text = db.scalar(select(DocumentText).where(DocumentText.document_id == document.id))

        if text and text.normalized_text:
            sources.append(serialize_document_text(text, document=document))

    return sources


def collect_conversation_sources(
    db: Session,
    *,
    patient_id: UUID,
    instance: MemorySystemInstance,
    cutoff_time: datetime,
) -> list[CanonicalSourceInput]:
    filters = [
        MemoryMessage.patient_id == patient_id,
        MemoryMessage.event_time <= cutoff_time,
    ]

    if instance.system_type not in {"csm", "csm_v3", "csm_v4"}:
        filters.extend(
            [
                MemoryMessage.system_instance_id == instance.id,
                MemoryConversation.system_instance_id == instance.id,
            ]
        )

    statement = (
        select(MemoryMessage, MemoryConversation, MemorySystemInstance)
        .join(MemoryConversation, MemoryMessage.conversation_id == MemoryConversation.id)
        .join(MemorySystemInstance, MemoryConversation.system_instance_id == MemorySystemInstance.id)
        .where(*filters)
        .order_by(MemoryMessage.event_time.asc(), MemoryMessage.sequence_number.asc())
    )
    rows = list(db.execute(statement).all())

    return [
        serialize_conversation_message(
            message,
            conversation=conversation,
            instance=message_instance,
            owning_system_instance_id=instance.id,
        )
        for message, conversation, message_instance in rows
    ]
