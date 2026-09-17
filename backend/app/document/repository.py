from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.document.models import (
    Document,
    DocumentArtifact,
    DocumentAuditEvent,
    DocumentPage,
    DocumentProcessingJob,
    DocumentProcessingRun,
    DocumentSection,
    DocumentText,
)
from app.patient.model import Patient
from app.patient_information.models import ClinicalEncounter


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


def get_owned_encounter(
    db: Session,
    *,
    doctor_id: UUID,
    patient_id: UUID,
    encounter_id: UUID,
) -> Optional[ClinicalEncounter]:
    statement = (
        select(ClinicalEncounter)
        .join(Patient, ClinicalEncounter.patient_id == Patient.id)
        .where(
            ClinicalEncounter.id == encounter_id,
            ClinicalEncounter.patient_id == patient_id,
            Patient.doctor_id == doctor_id,
        )
    )

    return db.scalar(statement)


def get_document_by_id(
    db: Session,
    *,
    document_id: UUID,
) -> Optional[Document]:
    return db.get(Document, document_id)


def get_processing_job_by_id(
    db: Session,
    *,
    job_id: UUID,
) -> Optional[DocumentProcessingJob]:
    return db.get(DocumentProcessingJob, job_id)


def get_processing_run_by_id(
    db: Session,
    *,
    run_id: UUID,
) -> Optional[DocumentProcessingRun]:
    return db.get(DocumentProcessingRun, run_id)


def get_owned_document(
    db: Session,
    *,
    doctor_id: UUID,
    patient_id: UUID,
    document_id: UUID,
) -> Optional[Document]:
    statement = (
        select(Document)
        .join(Patient, Document.patient_id == Patient.id)
        .where(
            Document.id == document_id,
            Document.patient_id == patient_id,
            Patient.doctor_id == doctor_id,
        )
    )

    return db.scalar(statement)


def list_owned_documents(
    db: Session,
    *,
    doctor_id: UUID,
    patient_id: UUID,
    offset: int,
    limit: int,
    include_archived: bool,
    document_type: Optional[str],
    processing_status: Optional[str],
    search: Optional[str],
) -> list[Document]:
    filters = build_document_filters(
        include_archived=include_archived,
        document_type=document_type,
        processing_status=processing_status,
        search=search,
    )
    statement = (
        select(Document)
        .join(Patient, Document.patient_id == Patient.id)
        .where(
            Document.patient_id == patient_id,
            Patient.doctor_id == doctor_id,
            *filters,
        )
        .order_by(Document.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    return list(db.scalars(statement).all())


def count_owned_documents(
    db: Session,
    *,
    doctor_id: UUID,
    patient_id: UUID,
    include_archived: bool,
    document_type: Optional[str],
    processing_status: Optional[str],
    search: Optional[str],
) -> int:
    filters = build_document_filters(
        include_archived=include_archived,
        document_type=document_type,
        processing_status=processing_status,
        search=search,
    )
    statement = (
        select(func.count())
        .select_from(Document)
        .join(Patient, Document.patient_id == Patient.id)
        .where(
            Document.patient_id == patient_id,
            Patient.doctor_id == doctor_id,
            *filters,
        )
    )

    return int(db.scalar(statement) or 0)


def create_document(
    db: Session,
    *,
    data: dict,
) -> Document:
    document = Document(**data)
    db.add(document)
    db.flush()

    return document


def update_document(
    db: Session,
    *,
    document: Document,
    data: dict,
) -> Document:
    for field, value in data.items():
        setattr(document, field, value)

    db.flush()

    return document


def create_audit_event(
    db: Session,
    *,
    document: Document,
    action: str,
    status: str,
    doctor_id: Optional[UUID],
    actor_type: str,
    metadata: Optional[dict] = None,
) -> DocumentAuditEvent:
    event = DocumentAuditEvent(
        document_id=document.id,
        patient_id=document.patient_id,
        doctor_id=doctor_id,
        action=action,
        status=status,
        actor_type=actor_type,
        metadata_json=metadata or {},
    )
    db.add(event)
    db.flush()

    return event


def find_duplicate_document(
    db: Session,
    *,
    patient_id: UUID,
    checksum: str,
    size_bytes: int,
    detected_content_type: str,
    exclude_document_id: Optional[UUID] = None,
) -> Optional[Document]:
    filters = [
        Document.patient_id == patient_id,
        Document.checksum_actual == checksum,
        Document.size_bytes_actual == size_bytes,
        Document.detected_content_type == detected_content_type,
        Document.is_active.is_(True),
        Document.verification_status == "verified",
    ]

    if exclude_document_id is not None:
        filters.append(Document.id != exclude_document_id)

    statement = (
        select(Document)
        .where(*filters)
        .order_by(Document.created_at.asc())
        .limit(1)
    )

    return db.scalar(statement)


def get_document_text(
    db: Session,
    *,
    document_id: UUID,
) -> Optional[DocumentText]:
    statement = select(DocumentText).where(DocumentText.document_id == document_id)

    return db.scalar(statement)


def list_document_pages(
    db: Session,
    *,
    document_id: UUID,
) -> list[DocumentPage]:
    statement = (
        select(DocumentPage)
        .where(DocumentPage.document_id == document_id)
        .order_by(DocumentPage.page_number.asc())
    )

    return list(db.scalars(statement).all())


def list_document_sections(
    db: Session,
    *,
    document_id: UUID,
) -> list[DocumentSection]:
    statement = (
        select(DocumentSection)
        .where(DocumentSection.document_id == document_id)
        .order_by(DocumentSection.section_index.asc())
    )

    return list(db.scalars(statement).all())


def list_document_artifacts(
    db: Session,
    *,
    document_id: UUID,
) -> list[DocumentArtifact]:
    statement = (
        select(DocumentArtifact)
        .where(DocumentArtifact.document_id == document_id)
        .order_by(DocumentArtifact.created_at.asc())
    )

    return list(db.scalars(statement).all())


def list_document_audit_events(
    db: Session,
    *,
    document_id: UUID,
) -> list[DocumentAuditEvent]:
    statement = (
        select(DocumentAuditEvent)
        .where(DocumentAuditEvent.document_id == document_id)
        .order_by(DocumentAuditEvent.created_at.desc())
    )

    return list(db.scalars(statement).all())


def count_document_pages(
    db: Session,
    *,
    document_id: UUID,
) -> int:
    statement = select(func.count()).select_from(DocumentPage).where(
        DocumentPage.document_id == document_id
    )

    return int(db.scalar(statement) or 0)


def count_document_sections(
    db: Session,
    *,
    document_id: UUID,
) -> int:
    statement = select(func.count()).select_from(DocumentSection).where(
        DocumentSection.document_id == document_id
    )

    return int(db.scalar(statement) or 0)


def count_document_artifacts(
    db: Session,
    *,
    document_id: UUID,
) -> int:
    statement = select(func.count()).select_from(DocumentArtifact).where(
        DocumentArtifact.document_id == document_id
    )

    return int(db.scalar(statement) or 0)


def create_processing_job(
    db: Session,
    *,
    data: dict,
) -> DocumentProcessingJob:
    job = DocumentProcessingJob(**data)
    db.add(job)
    db.flush()

    return job


def update_processing_job(
    db: Session,
    *,
    job: DocumentProcessingJob,
    data: dict,
) -> DocumentProcessingJob:
    for field, value in data.items():
        setattr(job, field, value)

    db.flush()

    return job


def create_processing_run(
    db: Session,
    *,
    data: dict,
) -> DocumentProcessingRun:
    run = DocumentProcessingRun(**data)
    db.add(run)
    db.flush()

    return run


def update_processing_run(
    db: Session,
    *,
    run: DocumentProcessingRun,
    data: dict,
) -> DocumentProcessingRun:
    for field, value in data.items():
        setattr(run, field, value)

    db.flush()

    return run


def list_processing_jobs(
    db: Session,
    *,
    document_id: UUID,
) -> list[DocumentProcessingJob]:
    statement = (
        select(DocumentProcessingJob)
        .where(DocumentProcessingJob.document_id == document_id)
        .order_by(DocumentProcessingJob.created_at.desc())
    )

    return list(db.scalars(statement).all())


def get_latest_processing_job(
    db: Session,
    *,
    document_id: UUID,
) -> Optional[DocumentProcessingJob]:
    statement = (
        select(DocumentProcessingJob)
        .where(DocumentProcessingJob.document_id == document_id)
        .order_by(DocumentProcessingJob.created_at.desc())
        .limit(1)
    )

    return db.scalar(statement)


def get_running_processing_job(
    db: Session,
    *,
    document_id: UUID,
) -> Optional[DocumentProcessingJob]:
    statement = (
        select(DocumentProcessingJob)
        .where(
            DocumentProcessingJob.document_id == document_id,
            DocumentProcessingJob.status.in_(["queued", "running", "retry_scheduled"]),
        )
        .order_by(DocumentProcessingJob.created_at.desc())
        .limit(1)
    )

    return db.scalar(statement)


def replace_extracted_document_content(
    db: Session,
    *,
    document_id: UUID,
    text_data: dict,
    pages: list[dict],
    sections: list[dict],
    artifacts: list[dict],
) -> None:
    db.execute(delete(DocumentText).where(DocumentText.document_id == document_id))
    db.execute(delete(DocumentPage).where(DocumentPage.document_id == document_id))
    db.execute(delete(DocumentSection).where(DocumentSection.document_id == document_id))
    db.execute(delete(DocumentArtifact).where(DocumentArtifact.document_id == document_id))

    db.add(DocumentText(document_id=document_id, **text_data))
    db.add_all(DocumentPage(document_id=document_id, **page) for page in pages)
    db.add_all(DocumentSection(document_id=document_id, **section) for section in sections)
    db.add_all(DocumentArtifact(document_id=document_id, **artifact) for artifact in artifacts)
    db.flush()


def build_document_filters(
    *,
    include_archived: bool,
    document_type: Optional[str],
    processing_status: Optional[str],
    search: Optional[str],
) -> list:
    filters = []

    if not include_archived:
        filters.append(Document.is_active.is_(True))

    if document_type:
        filters.append(Document.document_type == document_type)

    if processing_status:
        filters.append(Document.processing_status == processing_status)

    if search:
        pattern = f"%{search}%"
        filters.append(
            Document.title.ilike(pattern)
            | Document.original_filename.ilike(pattern)
            | Document.description.ilike(pattern)
        )

    return filters
