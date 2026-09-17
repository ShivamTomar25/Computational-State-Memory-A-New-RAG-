from __future__ import annotations

from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from app.memory_systems.common.canonical.hash import stable_content_hash
from app.memory_systems.common.schemas.canonical import CanonicalSourceInput


def serialize_patient_record(record, *, patient_id, subtype: str) -> CanonicalSourceInput:
    builders = {
        "condition": condition_text,
        "medication": medication_text,
        "allergy": allergy_text,
        "measurement": measurement_text,
        "encounter": encounter_text,
        "clinical_note": clinical_note_text,
    }
    content_text = builders[subtype](record)
    payload = model_payload(record)
    event_time = record_event_time(record, subtype)
    source = CanonicalSourceInput(
        patient_id=patient_id,
        source_type="patient_information",
        source_subtype=subtype,
        source_record_id=str(record.id),
        source_version=source_version(record),
        content_text=content_text,
        structured_payload=payload,
        event_time=event_time,
        valid_time=event_time,
        recorded_time=getattr(record, "recorded_at", None) or getattr(record, "created_at"),
        encounter_id=getattr(record, "encounter_id", None),
        visibility_scope="patient_shared",
    )

    return with_hash(source)


def serialize_document_metadata(document) -> CanonicalSourceInput:
    parts = [
        f"Document title: {document.title}" if document.title else None,
        f"Filename: {document.original_filename}",
        f"Document type: {document.document_type}",
        f"Document date: {document.document_date}" if document.document_date else None,
        f"Description: {document.description}" if document.description else None,
        f"Text extraction status: {document.text_extraction_status}",
        f"OCR requirement: {document.ocr_requirement_status}",
    ]
    content_text = ". ".join(part for part in parts if part)
    payload = model_payload(document)
    event_time = datetime_from_date(document.document_date) or document.created_at
    source = CanonicalSourceInput(
        patient_id=document.patient_id,
        source_type="document",
        source_subtype="document",
        source_record_id=str(document.id),
        source_version=source_version(document),
        content_text=content_text,
        structured_payload=payload,
        event_time=event_time,
        valid_time=event_time,
        recorded_time=document.created_at,
        document_id=document.id,
        encounter_id=document.encounter_id,
        visibility_scope="patient_shared",
    )

    return with_hash(source)


def serialize_document_section(section, *, document) -> CanonicalSourceInput:
    heading = f"Section heading: {section.heading}. " if section.heading else ""
    content_text = f"{heading}{section.normalized_text}".strip()
    payload = model_payload(section)
    payload["document"] = safe_document_payload(document)
    event_time = datetime_from_date(document.document_date) or section.created_at
    source = CanonicalSourceInput(
        patient_id=document.patient_id,
        source_type="document",
        source_subtype="section",
        source_record_id=str(section.id),
        source_version=source_version(section),
        content_text=content_text,
        structured_payload=payload,
        event_time=event_time,
        valid_time=event_time,
        recorded_time=section.created_at,
        document_id=document.id,
        section_id=section.id,
        encounter_id=document.encounter_id,
        visibility_scope="patient_shared",
    )

    return with_hash(source)


def serialize_document_page(page, *, document) -> CanonicalSourceInput:
    payload = model_payload(page)
    payload["document"] = safe_document_payload(document)
    event_time = datetime_from_date(document.document_date) or page.created_at
    source = CanonicalSourceInput(
        patient_id=document.patient_id,
        source_type="document",
        source_subtype="page",
        source_record_id=str(page.id),
        source_version=source_version(page),
        content_text=page.normalized_text,
        structured_payload=payload,
        event_time=event_time,
        valid_time=event_time,
        recorded_time=page.created_at,
        document_id=document.id,
        page_number=page.page_number,
        encounter_id=document.encounter_id,
        visibility_scope="patient_shared",
    )

    return with_hash(source)


def serialize_document_text(text, *, document) -> CanonicalSourceInput:
    payload = model_payload(text)
    payload["document"] = safe_document_payload(document)
    event_time = datetime_from_date(document.document_date) or text.created_at
    source = CanonicalSourceInput(
        patient_id=document.patient_id,
        source_type="document",
        source_subtype="extracted_text",
        source_record_id=str(text.id),
        source_version=source_version(text),
        content_text=text.normalized_text or "",
        structured_payload=payload,
        event_time=event_time,
        valid_time=event_time,
        recorded_time=text.created_at,
        document_id=document.id,
        encounter_id=document.encounter_id,
        visibility_scope="patient_shared",
    )

    return with_hash(source)


def serialize_conversation_message(message, *, conversation, instance, owning_system_instance_id=None) -> CanonicalSourceInput:
    subtype = f"{message.role}_message"
    source = CanonicalSourceInput(
        patient_id=message.patient_id,
        source_type="conversation",
        source_subtype=subtype,
        source_record_id=str(message.id),
        source_version=source_version(message),
        content_text=message.content,
        structured_payload={
            "role": message.role,
            "sequence_number": message.sequence_number,
            "generation_status": message.generation_status,
            "system_type": instance.system_type,
        },
        event_time=message.event_time,
        valid_time=message.event_time,
        recorded_time=message.created_at,
        conversation_id=conversation.id,
        message_id=message.id,
        role=message.role,
        owning_system_instance_id=owning_system_instance_id or instance.id,
        visibility_scope="system_private",
    )

    return with_hash(source)


def condition_text(record) -> str:
    parts = [
        f"Condition: {record.name}",
        f"Category: {record.category}",
        f"Clinical status: {record.clinical_status}",
        f"Verification status: {record.verification_status}",
        f"Severity: {record.severity}" if record.severity else None,
        f"Onset date: {record.onset_date}" if record.onset_date else None,
        f"Resolved date: {record.resolved_date}" if record.resolved_date else None,
        f"Notes: {record.notes}" if record.notes else None,
    ]

    return ". ".join(part for part in parts if part)


def medication_text(record) -> str:
    dosage = " ".join(str(value) for value in (record.dosage_value, record.dosage_unit) if value)
    parts = [
        f"Medication: {record.medication_name}",
        f"Generic name: {record.generic_name}" if record.generic_name else None,
        f"Dosage: {dosage}" if dosage else None,
        f"Frequency: {record.frequency}" if record.frequency else None,
        f"Route: {record.route}" if record.route else None,
        f"Status: {record.medication_status}",
        f"Start date: {record.start_date}" if record.start_date else None,
        f"End date: {record.end_date}" if record.end_date else None,
        f"Reason: {record.reason}" if record.reason else None,
    ]

    return ". ".join(part for part in parts if part)


def allergy_text(record) -> str:
    parts = [
        f"Allergy: {record.substance}",
        f"Type: {record.allergy_type}",
        f"Category: {record.category}" if record.category else None,
        f"Clinical status: {record.clinical_status}",
        f"Verification status: {record.verification_status}",
        f"Criticality: {record.criticality}" if record.criticality else None,
        f"Reaction: {record.reaction}" if record.reaction else None,
        f"Severity: {record.severity}" if record.severity else None,
    ]

    return ". ".join(part for part in parts if part)


def measurement_text(record) -> str:
    value = record.value_numeric if record.value_numeric is not None else record.value_text
    parts = [
        f"Measurement: {record.observation_name}",
        f"Value: {value}" if value is not None else None,
        f"Unit: {record.unit}" if record.unit else None,
        f"Observed at: {record.observed_at}",
        f"Status: {record.status}",
        f"Interpretation: {record.interpretation}" if record.interpretation else None,
        f"Notes: {record.notes}" if record.notes else None,
    ]

    return ". ".join(part for part in parts if part)


def encounter_text(record) -> str:
    parts = [
        f"Encounter type: {record.encounter_type}",
        f"Status: {record.status}",
        f"Started at: {record.started_at}",
        f"Ended at: {record.ended_at}" if record.ended_at else None,
        f"Chief complaint: {record.chief_complaint}" if record.chief_complaint else None,
        f"Summary: {record.summary}" if record.summary else None,
        f"Location: {record.location}" if record.location else None,
    ]

    return ". ".join(part for part in parts if part)


def clinical_note_text(record) -> str:
    parts = [
        f"Clinical note type: {record.note_type}",
        f"Title: {record.title}" if record.title else None,
        f"Authored at: {record.authored_at}",
        f"Status: {record.status}",
        record.content,
    ]

    return ". ".join(part for part in parts if part)


def with_hash(source: CanonicalSourceInput) -> CanonicalSourceInput:
    return CanonicalSourceInput(
        **{
            **source.__dict__,
            "content_hash": stable_content_hash(
                content_text=source.content_text,
                structured_payload=source.structured_payload,
            ),
        }
    )


def model_payload(record) -> dict:
    payload = {}

    for column in record.__table__.columns:
        value = getattr(record, column.name)
        payload[column.name] = json_safe(value)

    return payload


def json_safe(value):
    if isinstance(value, UUID):
        return str(value)

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    return value


def source_version(record) -> str:
    value = getattr(record, "updated_at", None) or getattr(record, "created_at", None)

    return value.isoformat() if value else "1"


def record_event_time(record, subtype: str) -> datetime:
    if subtype == "measurement":
        return record.observed_at

    if subtype == "encounter":
        return record.started_at

    if subtype == "clinical_note":
        return record.authored_at

    for field in ("recorded_at", "created_at"):
        value = getattr(record, field, None)

        if value:
            return value

    return datetime.now(timezone.utc)


def datetime_from_date(value: Optional[date]) -> Optional[datetime]:
    if value is None:
        return None

    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def safe_document_payload(document) -> dict:
    return {
        "id": str(document.id),
        "document_type": document.document_type,
        "document_date": document.document_date.isoformat()
        if document.document_date
        else None,
        "text_extraction_status": document.text_extraction_status,
        "ocr_requirement_status": document.ocr_requirement_status,
    }
