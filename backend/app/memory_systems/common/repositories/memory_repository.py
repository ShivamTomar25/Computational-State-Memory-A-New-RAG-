from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.memory_systems.common.models.memory import (
    CanonicalMemorySource,
    MemoryConversation,
    MemoryIngestionRun,
    MemoryIngestionRunItem,
    MemoryMessage,
    MemoryRetrievalItem,
    MemoryRetrievalRun,
    MemorySystemEvent,
    MemorySystemInstance,
    MemorySystemSourceLink,
)
from app.memory_systems.common.schemas.canonical import CanonicalSourceInput
from app.patient.model import Patient


def get_owned_patient(
    db: Session,
    *,
    doctor_id: UUID,
    patient_id: UUID,
) -> Optional[Patient]:
    statement = select(Patient).where(
        Patient.id == patient_id,
        Patient.doctor_id == doctor_id,
    )

    return db.scalar(statement)


def get_instance(
    db: Session,
    *,
    patient_id: UUID,
    system_type: str,
) -> Optional[MemorySystemInstance]:
    statement = select(MemorySystemInstance).where(
        MemorySystemInstance.patient_id == patient_id,
        MemorySystemInstance.system_type == system_type,
    )

    return db.scalar(statement)


def list_instances(
    db: Session,
    *,
    patient_id: UUID,
) -> list[MemorySystemInstance]:
    statement = (
        select(MemorySystemInstance)
        .where(MemorySystemInstance.patient_id == patient_id)
        .order_by(MemorySystemInstance.system_type.asc())
    )

    return list(db.scalars(statement).all())


def create_instance(
    db: Session,
    *,
    data: dict,
) -> MemorySystemInstance:
    instance = MemorySystemInstance(**data)
    db.add(instance)
    db.flush()

    return instance


def update_instance(
    db: Session,
    *,
    instance: MemorySystemInstance,
    data: dict,
) -> MemorySystemInstance:
    for field, value in data.items():
        setattr(instance, field, value)

    db.flush()

    return instance


def upsert_canonical_source(
    db: Session,
    *,
    source: CanonicalSourceInput,
) -> tuple[CanonicalMemorySource, bool]:
    statement = select(CanonicalMemorySource).where(
        CanonicalMemorySource.patient_id == source.patient_id,
        CanonicalMemorySource.source_type == source.source_type,
        CanonicalMemorySource.source_subtype == source.source_subtype,
        CanonicalMemorySource.source_record_id == source.source_record_id,
        CanonicalMemorySource.source_version == source.source_version,
        CanonicalMemorySource.visibility_scope == source.visibility_scope,
        CanonicalMemorySource.owning_system_instance_id == source.owning_system_instance_id,
    )
    existing = db.scalar(statement)

    if existing is not None:
        if not existing.is_active:
            existing.is_active = True
            existing.archived_at = None
            db.flush()

        return existing, False

    canonical = CanonicalMemorySource(
        patient_id=source.patient_id,
        source_type=source.source_type,
        source_subtype=source.source_subtype,
        source_record_id=source.source_record_id,
        source_version=source.source_version,
        content_text=source.content_text,
        structured_payload=source.structured_payload,
        event_time=source.event_time,
        valid_time=source.valid_time,
        recorded_time=source.recorded_time,
        document_id=source.document_id,
        page_number=source.page_number,
        section_id=source.section_id,
        encounter_id=source.encounter_id,
        conversation_id=source.conversation_id,
        message_id=source.message_id,
        role=source.role,
        owning_system_instance_id=source.owning_system_instance_id,
        visibility_scope=source.visibility_scope,
        content_hash=source.content_hash,
        is_active=True,
        archived_at=None,
    )
    db.add(canonical)
    db.flush()

    return canonical, True


def list_active_sources_for_instance(
    db: Session,
    *,
    patient_id: UUID,
    system_instance_id: UUID,
) -> list[CanonicalMemorySource]:
    statement = (
        select(CanonicalMemorySource)
        .where(
            CanonicalMemorySource.patient_id == patient_id,
            CanonicalMemorySource.is_active.is_(True),
            (
                (CanonicalMemorySource.visibility_scope == "patient_shared")
                | (
                    (CanonicalMemorySource.visibility_scope == "system_private")
                    & (CanonicalMemorySource.owning_system_instance_id == system_instance_id)
                )
            ),
        )
        .order_by(
            CanonicalMemorySource.source_type.asc(),
            CanonicalMemorySource.event_time.asc(),
            CanonicalMemorySource.id.asc(),
        )
    )

    return list(db.scalars(statement).all())


def create_or_update_source_link(
    db: Session,
    *,
    system_instance_id: UUID,
    canonical_source_id: UUID,
    native_record_type: Optional[str],
    native_record_id: Optional[UUID],
    source_hash: str,
    ingestion_status: str,
    indexed_at: Optional[datetime],
) -> MemorySystemSourceLink:
    statement = select(MemorySystemSourceLink).where(
        MemorySystemSourceLink.system_instance_id == system_instance_id,
        MemorySystemSourceLink.canonical_source_id == canonical_source_id,
        MemorySystemSourceLink.source_hash == source_hash,
    )
    link = db.scalar(statement)

    if link is None:
        link = MemorySystemSourceLink(
            system_instance_id=system_instance_id,
            canonical_source_id=canonical_source_id,
            native_record_type=native_record_type,
            native_record_id=native_record_id,
            source_hash=source_hash,
            ingestion_status=ingestion_status,
            indexed_at=indexed_at,
            deactivated_at=None,
        )
        db.add(link)
    else:
        link.native_record_type = native_record_type
        link.native_record_id = native_record_id
        link.ingestion_status = ingestion_status
        link.indexed_at = indexed_at
        link.deactivated_at = None

    db.flush()

    return link


def create_ingestion_run(
    db: Session,
    *,
    data: dict,
) -> MemoryIngestionRun:
    run = MemoryIngestionRun(**data)
    db.add(run)
    db.flush()

    return run


def update_ingestion_run(
    db: Session,
    *,
    run: MemoryIngestionRun,
    data: dict,
) -> MemoryIngestionRun:
    for field, value in data.items():
        setattr(run, field, value)

    db.flush()

    return run


def add_ingestion_run_item(
    db: Session,
    *,
    data: dict,
) -> MemoryIngestionRunItem:
    item = MemoryIngestionRunItem(**data)
    db.add(item)
    db.flush()

    return item


def list_ingestion_runs(
    db: Session,
    *,
    system_instance_id: UUID,
) -> list[MemoryIngestionRun]:
    statement = (
        select(MemoryIngestionRun)
        .where(MemoryIngestionRun.system_instance_id == system_instance_id)
        .order_by(MemoryIngestionRun.created_at.desc())
    )

    return list(db.scalars(statement).all())


def get_ingestion_run(
    db: Session,
    *,
    system_instance_id: UUID,
    run_id: UUID,
) -> Optional[MemoryIngestionRun]:
    statement = select(MemoryIngestionRun).where(
        MemoryIngestionRun.id == run_id,
        MemoryIngestionRun.system_instance_id == system_instance_id,
    )

    return db.scalar(statement)


def list_ingestion_run_items(
    db: Session,
    *,
    run_id: UUID,
) -> list[MemoryIngestionRunItem]:
    statement = select(MemoryIngestionRunItem).where(
        MemoryIngestionRunItem.run_id == run_id
    )

    return list(db.scalars(statement).all())


def create_conversation(
    db: Session,
    *,
    data: dict,
) -> MemoryConversation:
    conversation = MemoryConversation(**data)
    db.add(conversation)
    db.flush()

    return conversation


def list_conversations(
    db: Session,
    *,
    system_instance_id: UUID,
) -> list[MemoryConversation]:
    statement = (
        select(MemoryConversation)
        .where(MemoryConversation.system_instance_id == system_instance_id)
        .order_by(MemoryConversation.updated_at.desc())
    )

    return list(db.scalars(statement).all())


def get_conversation(
    db: Session,
    *,
    system_instance_id: UUID,
    conversation_id: UUID,
) -> Optional[MemoryConversation]:
    statement = select(MemoryConversation).where(
        MemoryConversation.id == conversation_id,
        MemoryConversation.system_instance_id == system_instance_id,
    )

    return db.scalar(statement)


def create_message(
    db: Session,
    *,
    conversation: MemoryConversation,
    data: dict,
) -> MemoryMessage:
    next_sequence = get_next_message_sequence(
        db=db,
        conversation_id=conversation.id,
    )
    message = MemoryMessage(
        conversation_id=conversation.id,
        patient_id=conversation.patient_id,
        system_instance_id=conversation.system_instance_id,
        sequence_number=next_sequence,
        **data,
    )
    conversation.last_message_at = message.event_time
    db.add(message)
    db.flush()

    return message


def list_messages(
    db: Session,
    *,
    conversation_id: UUID,
) -> list[MemoryMessage]:
    statement = (
        select(MemoryMessage)
        .where(MemoryMessage.conversation_id == conversation_id)
        .order_by(MemoryMessage.sequence_number.asc())
    )

    return list(db.scalars(statement).all())


def get_next_message_sequence(
    db: Session,
    *,
    conversation_id: UUID,
) -> int:
    statement = select(func.max(MemoryMessage.sequence_number)).where(
        MemoryMessage.conversation_id == conversation_id
    )

    return int(db.scalar(statement) or 0) + 1


def create_retrieval_run(
    db: Session,
    *,
    data: dict,
) -> MemoryRetrievalRun:
    run = MemoryRetrievalRun(**data)
    db.add(run)
    db.flush()

    return run


def add_retrieval_item(
    db: Session,
    *,
    data: dict,
) -> MemoryRetrievalItem:
    item = MemoryRetrievalItem(**data)
    db.add(item)
    db.flush()

    return item


def update_message_retrieval(
    db: Session,
    *,
    message: MemoryMessage,
    retrieval_run_id: UUID,
) -> MemoryMessage:
    message.retrieval_run_id = retrieval_run_id
    db.flush()

    return message


def create_event(
    db: Session,
    *,
    data: dict,
) -> MemorySystemEvent:
    event = MemorySystemEvent(**data)
    db.add(event)
    db.flush()

    return event


def count_sources_by_type(
    db: Session,
    *,
    patient_id: UUID,
    system_instance_id: UUID,
) -> dict:
    sources = list_active_sources_for_instance(
        db=db,
        patient_id=patient_id,
        system_instance_id=system_instance_id,
    )
    counts = {
        "patient_information": 0,
        "document": 0,
        "conversation": 0,
    }

    for source in sources:
        counts[source.source_type] = counts.get(source.source_type, 0) + 1

    return counts


def count_links(
    db: Session,
    *,
    system_instance_id: UUID,
) -> int:
    statement = select(func.count()).select_from(MemorySystemSourceLink).where(
        MemorySystemSourceLink.system_instance_id == system_instance_id,
        MemorySystemSourceLink.deactivated_at.is_(None),
    )

    return int(db.scalar(statement) or 0)


def delete_source_links_for_instance(
    db: Session,
    *,
    system_instance_id: UUID,
) -> None:
    db.execute(
        delete(MemorySystemSourceLink).where(
            MemorySystemSourceLink.system_instance_id == system_instance_id
        )
    )
    db.flush()
