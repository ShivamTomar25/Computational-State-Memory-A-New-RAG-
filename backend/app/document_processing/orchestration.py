from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.document import repository
from app.document.audit import record_document_audit
from app.document.exceptions import (
    DocumentError,
    DocumentNotFound,
    ProcessingNotAllowed,
    TextExtractionFailed,
    UnsupportedDocumentFormat,
)
from app.document.lifecycle import ensure_processing_can_start
from app.document.models import Document, DocumentProcessingJob
from app.document_processing.artifact_service import persist_processing_artifacts
from app.document_processing.detectors.file_signature import detect_file_signature
from app.document_processing.detectors.ocr_requirement import classify_ocr_requirement
from app.document_processing.detectors.pdf_text_quality import assess_text_quality
from app.document_processing.extractors.factory import extract_text_by_family
from app.document_processing.page_builder import build_page_rows
from app.document_processing.section_builder import build_section_rows
from app.storage.exceptions import StorageProviderError
from app.storage.interface import StorageProvider


PROCESSOR_NAME = "sustha_document_processor"
PROCESSOR_VERSION = "1.0"


def process_owned_document(
    db: Session,
    *,
    doctor_id: UUID,
    patient_id: UUID,
    document_id: UUID,
    storage_provider: StorageProvider,
    force: bool = False,
) -> DocumentProcessingJob:
    document = repository.get_owned_document(
        db=db,
        doctor_id=doctor_id,
        patient_id=patient_id,
        document_id=document_id,
    )

    if document is None:
        raise DocumentNotFound("Document not found.")

    return process_document(
        db=db,
        document=document,
        doctor_id=doctor_id,
        storage_provider=storage_provider,
        force=force,
    )


def process_document(
    db: Session,
    *,
    document: Document,
    doctor_id: UUID,
    storage_provider: StorageProvider,
    force: bool = False,
) -> DocumentProcessingJob:
    if not force and document.processing_status in {
        "completed",
        "partially_completed",
        "awaiting_ocr",
    }:
        latest_job = repository.get_latest_processing_job(
            db=db,
            document_id=document.id,
        )

        if latest_job is not None:
            return latest_job

    if not force:
        running_job = repository.get_running_processing_job(
            db=db,
            document_id=document.id,
        )

        if running_job is not None:
            raise ProcessingNotAllowed("Document processing is already running.")

    ensure_processing_can_start(document)

    now = utc_now()
    job = repository.create_processing_job(
        db=db,
        data={
            "document_id": document.id,
            "patient_id": document.patient_id,
            "job_type": "process_document",
            "status": "running",
            "attempt_number": 1,
            "max_attempts": settings.document_processing_max_attempts,
            "queued_at": now,
            "started_at": now,
            "completed_at": None,
            "next_retry_at": None,
            "failure_code": None,
            "failure_reason": None,
            "worker_id": "local",
            "correlation_id": None,
            "input_version": document.storage_object_version,
            "processor_name": PROCESSOR_NAME,
            "processor_version": PROCESSOR_VERSION,
        },
    )
    run = repository.create_processing_run(
        db=db,
        data={
            "document_id": document.id,
            "pipeline_version": settings.document_processing_pipeline_version,
            "input_checksum": document.checksum_actual,
            "input_object_version": document.storage_object_version,
            "started_at": now,
            "completed_at": None,
            "status": "running",
            "extractor_name": None,
            "extractor_version": None,
            "quality_status": None,
            "ocr_requirement_status": None,
            "failure_code": None,
            "failure_reason": None,
        },
    )
    repository.update_document(
        db=db,
        document=document,
        data={
            "processing_status": "processing",
            "text_extraction_status": "extracting",
            "failure_code": None,
            "failure_reason": None,
            "processing_started_at": now,
            "processing_completed_at": None,
        },
    )
    record_document_audit(
        db=db,
        document=document,
        action="processing_started",
        status="running",
        doctor_id=doctor_id,
    )
    db.commit()

    try:
        finish_processing_success(
            db=db,
            document=document,
            job_id=job.id,
            run_id=run.id,
            doctor_id=doctor_id,
            storage_provider=storage_provider,
        )
    except Exception as error:
        finish_processing_failure(
            db=db,
            document_id=document.id,
            job_id=job.id,
            run_id=run.id,
            doctor_id=doctor_id,
            error=error,
        )

    refreshed_job = repository.get_processing_job_by_id(db=db, job_id=job.id)

    if refreshed_job is None:
        raise DocumentNotFound("Processing job not found.")

    return refreshed_job


def finish_processing_success(
    *,
    db: Session,
    document: Document,
    job_id: UUID,
    run_id: UUID,
    doctor_id: UUID,
    storage_provider: StorageProvider,
) -> None:
    content = storage_provider.download_bytes(
        object_path=document.storage_object_path,
        max_bytes=settings.document_max_file_size_bytes,
    )
    signature = detect_file_signature(
        content=content,
        filename=document.original_filename,
        declared_content_type=document.detected_content_type or document.declared_content_type,
    )
    extraction = extract_text_by_family(
        family=signature.family,
        content=content,
    )
    quality = assess_text_quality(extraction.pages)
    ocr_requirement = classify_ocr_requirement(quality)
    page_rows = build_page_rows(extraction.pages)
    section_rows = build_section_rows(extraction)
    metadata = {
        "document_id": str(document.id),
        "pipeline_version": settings.document_processing_pipeline_version,
        "processor_name": PROCESSOR_NAME,
        "processor_version": PROCESSOR_VERSION,
        "detected_content_type": signature.content_type,
        "extraction_method": extraction.extraction_method,
        "extractor_name": extraction.extractor_name,
        "extractor_version": extraction.extractor_version,
        "quality_status": quality.status,
        "quality_score": quality.score,
        "ocr_requirement_status": ocr_requirement.status,
        "ocr_requirement_reason": ocr_requirement.reason,
        "page_count": quality.page_count,
        "character_count": quality.character_count,
        "word_count": quality.word_count,
        "empty_page_count": quality.empty_page_count,
    }
    artifact_rows = persist_processing_artifacts(
        document=document,
        raw_text=extraction.raw_text,
        normalized_text=extraction.normalized_text,
        metadata=metadata,
        storage_provider=storage_provider,
        processor_name=PROCESSOR_NAME,
        processor_version=PROCESSOR_VERSION,
    )
    raw_text_path = find_artifact_path(artifact_rows, "raw_extracted_text")
    normalized_text_path = find_artifact_path(artifact_rows, "normalized_text")
    text_status = choose_text_status(quality.status, ocr_requirement.status)
    processing_status = choose_processing_status(quality.status, ocr_requirement.status)
    now = utc_now()
    job = repository.get_processing_job_by_id(db=db, job_id=job_id)
    run = repository.get_processing_run_by_id(db=db, run_id=run_id)

    if job is None or run is None:
        raise DocumentNotFound("Processing job not found.")

    repository.replace_extracted_document_content(
        db=db,
        document_id=document.id,
        text_data={
            "extraction_method": extraction.extraction_method,
            "extractor_name": extraction.extractor_name,
            "extractor_version": extraction.extractor_version,
            "raw_text_object_path": raw_text_path,
            "normalized_text_object_path": normalized_text_path,
            "normalized_text": extraction.normalized_text,
            "character_count": quality.character_count,
            "word_count": quality.word_count,
            "page_count": quality.page_count,
            "detected_language": None,
            "quality_score": quality.score,
            "quality_status": quality.status,
        },
        pages=page_rows,
        sections=section_rows,
        artifacts=artifact_rows,
    )
    repository.update_document(
        db=db,
        document=document,
        data={
            "processing_status": processing_status,
            "text_extraction_status": text_status,
            "ocr_requirement_status": ocr_requirement.status,
            "failure_code": None,
            "failure_reason": None,
            "processing_completed_at": now,
        },
    )
    repository.update_processing_job(
        db=db,
        job=job,
        data={
            "status": "succeeded",
            "completed_at": now,
            "failure_code": None,
            "failure_reason": None,
        },
    )
    repository.update_processing_run(
        db=db,
        run=run,
        data={
            "status": "succeeded",
            "completed_at": now,
            "extractor_name": extraction.extractor_name,
            "extractor_version": extraction.extractor_version,
            "quality_status": quality.status,
            "ocr_requirement_status": ocr_requirement.status,
            "failure_code": None,
            "failure_reason": None,
        },
    )
    record_document_audit(
        db=db,
        document=document,
        action="text_extracted",
        status=text_status,
        doctor_id=doctor_id,
        metadata={
            "quality_status": quality.status,
            "ocr_requirement_status": ocr_requirement.status,
        },
    )

    if ocr_requirement.status in {"required", "likely_required", "mixed_document"}:
        record_document_audit(
            db=db,
            document=document,
            action="ocr_required",
            status=ocr_requirement.status,
            doctor_id=doctor_id,
            metadata={"reason": ocr_requirement.reason},
        )

    record_document_audit(
        db=db,
        document=document,
        action="processing_completed",
        status=processing_status,
        doctor_id=doctor_id,
    )
    db.commit()


def finish_processing_failure(
    *,
    db: Session,
    document_id: UUID,
    job_id: UUID,
    run_id: UUID,
    doctor_id: UUID,
    error: Exception,
) -> None:
    document = repository.get_document_by_id(db=db, document_id=document_id)
    job = repository.get_processing_job_by_id(db=db, job_id=job_id)
    run = repository.get_processing_run_by_id(db=db, run_id=run_id)

    if document is None or job is None or run is None:
        db.rollback()
        return

    failure_code = error.__class__.__name__
    failure_reason = str(error)[:500] or "Document processing failed."
    now = utc_now()
    text_status = "not_supported" if isinstance(error, UnsupportedDocumentFormat) else "failed"

    if isinstance(error, StorageProviderError):
        failure_reason = "Could not read document from storage."
    elif isinstance(error, DocumentError):
        failure_reason = str(error)[:500] or failure_reason
    else:
        failure_code = TextExtractionFailed.__name__
        failure_reason = "Document text extraction failed."

    repository.update_document(
        db=db,
        document=document,
        data={
            "processing_status": "failed",
            "text_extraction_status": text_status,
            "ocr_requirement_status": "unsupported" if text_status == "not_supported" else "not_evaluated",
            "failure_code": failure_code,
            "failure_reason": failure_reason,
            "processing_completed_at": now,
        },
    )
    repository.update_processing_job(
        db=db,
        job=job,
        data={
            "status": "failed",
            "completed_at": now,
            "failure_code": failure_code,
            "failure_reason": failure_reason,
        },
    )
    repository.update_processing_run(
        db=db,
        run=run,
        data={
            "status": "failed",
            "completed_at": now,
            "failure_code": failure_code,
            "failure_reason": failure_reason,
        },
    )
    record_document_audit(
        db=db,
        document=document,
        action="processing_failed",
        status="failed",
        doctor_id=doctor_id,
        metadata={"failure_code": failure_code},
    )
    db.commit()


def choose_text_status(
    quality_status: str,
    ocr_status: str,
) -> str:
    if ocr_status == "required":
        return "awaiting_ocr"

    if quality_status == "unusable":
        return "no_text_found"

    if quality_status == "low":
        return "low_quality_text"

    return "extracted"


def choose_processing_status(
    quality_status: str,
    ocr_status: str,
) -> str:
    if ocr_status == "required":
        return "awaiting_ocr"

    if quality_status == "low" or ocr_status in {"likely_required", "mixed_document"}:
        return "partially_completed"

    return "completed"


def find_artifact_path(
    artifacts: list[dict],
    artifact_type: str,
) -> Optional[str]:
    for artifact in artifacts:
        if artifact["artifact_type"] == artifact_type:
            return artifact["storage_object_path"]

    return None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
