from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.doctor.model import Doctor
from app.document import repository
from app.document.audit import record_document_audit
from app.document.exceptions import (
    DocumentChecksumMismatch,
    DocumentContentTypeMismatch,
    DocumentNotFound,
    DocumentObjectMissing,
    DocumentSizeMismatch,
    EncounterDocumentMismatch,
    InvalidDocumentDate,
    InvalidDocumentType,
)
from app.document.lifecycle import (
    ensure_document_can_be_read,
    ensure_metadata_can_change,
    ensure_upload_can_complete,
)
from app.document.models import Document
from app.document.schemas import (
    DocumentDetailResponse,
    DocumentDirectUploadResponse,
    DocumentListResponse,
    DocumentProcessingStatusResponse,
    DocumentReconciliationIssue,
    DocumentReconciliationResponse,
    DocumentSummaryResponse,
    DocumentUpdate,
    DocumentUploadCompleteRequest,
    DocumentUploadInitiateRequest,
    DocumentUploadInitiateResponse,
    SignedDocumentUrlResponse,
)
from app.document.validators import (
    normalize_description,
    normalize_document_type,
    normalize_sha256,
    normalize_title,
    validate_document_date,
)
from app.document_processing.jobs import document_job_dispatcher
from app.document_processing.orchestration import process_document
from app.document_processing.detectors.file_signature import detect_file_signature
from app.storage.exceptions import StorageProviderError
from app.storage.file_policy import get_document_file_policy
from app.storage.interface import StorageProvider
from app.storage.path_builder import build_original_document_path
from app.storage.schemas import UploadFileMetadata


def initiate_document_upload(
    db: Session,
    *,
    doctor: Doctor,
    patient_id: UUID,
    upload_data: DocumentUploadInitiateRequest,
    storage_provider: StorageProvider,
) -> DocumentUploadInitiateResponse:
    ensure_owned_patient(
        db=db,
        doctor_id=doctor.id,
        patient_id=patient_id,
    )
    validate_owned_encounter(
        db=db,
        doctor_id=doctor.id,
        patient_id=patient_id,
        encounter_id=upload_data.encounter_id,
    )
    policy_result = get_document_file_policy().validate_upload_metadata(
        UploadFileMetadata(
            filename=upload_data.original_filename,
            content_type=upload_data.content_type,
            size_bytes=upload_data.size_bytes,
            checksum_sha256=upload_data.checksum,
        )
    )
    checksum = normalize_sha256(upload_data.checksum)
    document_id = uuid4()
    deadline = utc_now() + timedelta(
        seconds=settings.document_upload_completion_deadline_seconds
    )
    object_path = build_original_document_path(
        environment=settings.document_storage_environment,
        patient_id=patient_id,
        document_id=document_id,
        filename=policy_result.safe_filename,
    )

    try:
        document = repository.create_document(
            db=db,
            data={
                "id": document_id,
                "patient_id": patient_id,
                "uploaded_by_doctor_id": doctor.id,
                "encounter_id": upload_data.encounter_id,
                "document_type": normalize_document_type(upload_data.document_type),
                "title": normalize_title(upload_data.title),
                "description": normalize_description(upload_data.description),
                "original_filename": upload_data.original_filename.strip(),
                "safe_filename": policy_result.safe_filename,
                "file_extension": policy_result.extension,
                "declared_content_type": policy_result.normalized_content_type,
                "detected_content_type": None,
                "size_bytes_expected": policy_result.size_bytes,
                "size_bytes_actual": None,
                "checksum_algorithm": "sha256" if checksum else None,
                "checksum_expected": checksum,
                "checksum_actual": None,
                "duplicate_of_document_id": None,
                "storage_provider": storage_provider.provider_name,
                "storage_bucket": storage_provider.bucket,
                "storage_object_path": object_path,
                "storage_object_version": None,
                "storage_etag": None,
                "document_date": validate_document_date(upload_data.document_date),
                "source_type": "doctor_upload",
                "upload_status": "pending_upload",
                "verification_status": "not_started",
                "processing_status": "not_started",
                "text_extraction_status": "not_started",
                "ocr_requirement_status": "not_evaluated",
                "failure_code": None,
                "failure_reason": None,
                "replaces_document_id": upload_data.replaces_document_id,
                "superseded_by_document_id": None,
                "version_number": 1,
                "is_current_version": True,
                "is_active": True,
                "upload_deadline_at": deadline,
                "uploaded_at": None,
                "verified_at": None,
                "processing_started_at": None,
                "processing_completed_at": None,
                "archived_at": None,
            },
        )
        signed_upload = storage_provider.create_signed_upload(
            object_path=object_path,
            content_type=policy_result.normalized_content_type,
        )
        record_document_audit(
            db=db,
            document=document,
            action="upload_initiated",
            status="pending_upload",
            doctor_id=doctor.id,
        )
        db.commit()

        return DocumentUploadInitiateResponse(
            document_id=document.id,
            upload_status=document.upload_status,
            verification_status=document.verification_status,
            processing_status=document.processing_status,
            object_path=document.storage_object_path,
            upload=signed_upload,
            completion_endpoint=f"/api/patients/{patient_id}/documents/{document.id}/complete",
            upload_deadline_at=document.upload_deadline_at,
        )

    except IntegrityError as error:
        db.rollback()
        raise InvalidDocumentType("Document upload could not be created.") from error


def complete_document_upload(
    db: Session,
    *,
    doctor: Doctor,
    patient_id: UUID,
    document_id: UUID,
    completion_data: DocumentUploadCompleteRequest,
    storage_provider: StorageProvider,
) -> DocumentDetailResponse:
    document = get_owned_document_or_raise(
        db=db,
        doctor_id=doctor.id,
        patient_id=patient_id,
        document_id=document_id,
    )
    ensure_upload_can_complete(document)

    content = download_uploaded_document(document=document, storage_provider=storage_provider)
    verify_uploaded_content(
        document=document,
        content=content,
        checksum_override=completion_data.checksum,
    )
    metadata = safe_get_metadata(
        storage_provider=storage_provider,
        object_path=document.storage_object_path,
    )
    actual_checksum = sha256_hex(content)
    duplicate = repository.find_duplicate_document(
        db=db,
        patient_id=patient_id,
        checksum=actual_checksum,
        size_bytes=len(content),
        detected_content_type=document.detected_content_type or document.declared_content_type,
        exclude_document_id=document.id,
    )
    now = utc_now()
    repository.update_document(
        db=db,
        document=document,
        data={
            "upload_status": "uploaded",
            "verification_status": "verified",
            "size_bytes_actual": len(content),
            "checksum_algorithm": "sha256",
            "checksum_actual": actual_checksum,
            "checksum_expected": normalize_sha256(completion_data.checksum)
            or document.checksum_expected,
            "duplicate_of_document_id": duplicate.id if duplicate else None,
            "storage_etag": metadata.etag if metadata else None,
            "uploaded_at": now,
            "verified_at": now,
            "failure_code": None,
            "failure_reason": None,
        },
    )
    record_document_audit(
        db=db,
        document=document,
        action="upload_completed",
        status="uploaded",
        doctor_id=doctor.id,
    )
    record_document_audit(
        db=db,
        document=document,
        action="upload_verified",
        status="verified",
        doctor_id=doctor.id,
    )
    db.commit()
    db.refresh(document)
    process_document(
        db=db,
        document=document,
        doctor_id=doctor.id,
        storage_provider=storage_provider,
    )
    db.refresh(document)

    return build_document_detail_response(db=db, document=document)


def direct_upload_document(
    db: Session,
    *,
    doctor: Doctor,
    patient_id: UUID,
    original_filename: str,
    content_type: str,
    content: bytes,
    document_type: str,
    title: Optional[str],
    description: Optional[str],
    document_date: Optional[date],
    encounter_id: Optional[UUID],
    storage_provider: StorageProvider,
) -> DocumentDirectUploadResponse:
    ensure_owned_patient(
        db=db,
        doctor_id=doctor.id,
        patient_id=patient_id,
    )
    validate_owned_encounter(
        db=db,
        doctor_id=doctor.id,
        patient_id=patient_id,
        encounter_id=encounter_id,
    )
    policy_result = get_document_file_policy().validate_upload_metadata(
        UploadFileMetadata(
            filename=original_filename,
            content_type=content_type,
            size_bytes=len(content),
            checksum_sha256=sha256_hex(content),
        )
    )
    signature = detect_file_signature(
        content=content,
        filename=original_filename,
        declared_content_type=policy_result.normalized_content_type,
    )

    if signature.content_type != policy_result.normalized_content_type:
        raise DocumentContentTypeMismatch("File content does not match the declared content type.")

    document_id = uuid4()
    object_path = build_original_document_path(
        environment=settings.document_storage_environment,
        patient_id=patient_id,
        document_id=document_id,
        filename=policy_result.safe_filename,
    )
    actual_checksum = sha256_hex(content)
    duplicate = repository.find_duplicate_document(
        db=db,
        patient_id=patient_id,
        checksum=actual_checksum,
        size_bytes=len(content),
        detected_content_type=signature.content_type,
    )
    upload_result = storage_provider.upload_bytes(
        object_path=object_path,
        content=content,
        content_type=signature.content_type,
        overwrite=False,
        metadata={
            "patient_id": str(patient_id),
            "document_id": str(document_id),
            "uploaded_by_doctor_id": str(doctor.id),
        },
    )
    metadata = safe_get_metadata(
        storage_provider=storage_provider,
        object_path=object_path,
    )
    now = utc_now()

    document = repository.create_document(
        db=db,
        data={
            "id": document_id,
            "patient_id": patient_id,
            "uploaded_by_doctor_id": doctor.id,
            "encounter_id": encounter_id,
            "document_type": normalize_document_type(document_type),
            "title": normalize_title(title),
            "description": normalize_description(description),
            "original_filename": original_filename.strip(),
            "safe_filename": policy_result.safe_filename,
            "file_extension": signature.extension,
            "declared_content_type": policy_result.normalized_content_type,
            "detected_content_type": signature.content_type,
            "size_bytes_expected": len(content),
            "size_bytes_actual": len(content),
            "checksum_algorithm": "sha256",
            "checksum_expected": actual_checksum,
            "checksum_actual": actual_checksum,
            "duplicate_of_document_id": duplicate.id if duplicate else None,
            "storage_provider": upload_result.provider,
            "storage_bucket": upload_result.bucket,
            "storage_object_path": upload_result.object_path,
            "storage_object_version": None,
            "storage_etag": metadata.etag if metadata else None,
            "document_date": validate_document_date(document_date),
            "source_type": "doctor_upload",
            "upload_status": "uploaded",
            "verification_status": "verified",
            "processing_status": "not_started",
            "text_extraction_status": "not_started",
            "ocr_requirement_status": "not_evaluated",
            "failure_code": None,
            "failure_reason": None,
            "replaces_document_id": None,
            "superseded_by_document_id": None,
            "version_number": 1,
            "is_current_version": True,
            "is_active": True,
            "upload_deadline_at": now,
            "uploaded_at": now,
            "verified_at": now,
            "processing_started_at": None,
            "processing_completed_at": None,
            "archived_at": None,
        },
    )
    record_document_audit(
        db=db,
        document=document,
        action="upload_completed",
        status="uploaded",
        doctor_id=doctor.id,
    )
    record_document_audit(
        db=db,
        document=document,
        action="upload_verified",
        status="verified",
        doctor_id=doctor.id,
    )
    db.commit()
    db.refresh(document)
    process_document(
        db=db,
        document=document,
        doctor_id=doctor.id,
        storage_provider=storage_provider,
    )
    db.refresh(document)

    return DocumentDirectUploadResponse(
        document=build_document_detail_response(db=db, document=document),
        duplicate_warning="This file matches an existing active patient document."
        if duplicate
        else None,
    )


def list_documents(
    db: Session,
    *,
    doctor: Doctor,
    patient_id: UUID,
    page: int,
    page_size: int,
    include_archived: bool,
    document_type: Optional[str],
    processing_status: Optional[str],
    search: Optional[str],
) -> DocumentListResponse:
    ensure_owned_patient(
        db=db,
        doctor_id=doctor.id,
        patient_id=patient_id,
    )
    offset = (page - 1) * page_size
    normalized_type = normalize_document_type(document_type) if document_type else None
    normalized_search = search.strip() if search and search.strip() else None
    total = repository.count_owned_documents(
        db=db,
        doctor_id=doctor.id,
        patient_id=patient_id,
        include_archived=include_archived,
        document_type=normalized_type,
        processing_status=processing_status,
        search=normalized_search,
    )
    documents = repository.list_owned_documents(
        db=db,
        doctor_id=doctor.id,
        patient_id=patient_id,
        offset=offset,
        limit=page_size,
        include_archived=include_archived,
        document_type=normalized_type,
        processing_status=processing_status,
        search=normalized_search,
    )

    return DocumentListResponse(
        items=[DocumentSummaryResponse.model_validate(document) for document in documents],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if total else 0,
    )


def get_document_detail(
    db: Session,
    *,
    doctor: Doctor,
    patient_id: UUID,
    document_id: UUID,
) -> DocumentDetailResponse:
    document = get_owned_document_or_raise(
        db=db,
        doctor_id=doctor.id,
        patient_id=patient_id,
        document_id=document_id,
    )

    return build_document_detail_response(db=db, document=document)


def update_document_metadata(
    db: Session,
    *,
    doctor: Doctor,
    patient_id: UUID,
    document_id: UUID,
    update_data: DocumentUpdate,
) -> DocumentDetailResponse:
    document = get_owned_document_or_raise(
        db=db,
        doctor_id=doctor.id,
        patient_id=patient_id,
        document_id=document_id,
    )
    ensure_metadata_can_change(document)
    values = update_data.model_dump(exclude_unset=True)
    cleaned_values = {}

    if "document_type" in values:
        cleaned_values["document_type"] = normalize_document_type(values["document_type"])

    if "title" in values:
        cleaned_values["title"] = normalize_title(values["title"])

    if "description" in values:
        cleaned_values["description"] = normalize_description(values["description"])

    if "document_date" in values:
        cleaned_values["document_date"] = validate_document_date(values["document_date"])

    if "encounter_id" in values:
        validate_owned_encounter(
            db=db,
            doctor_id=doctor.id,
            patient_id=patient_id,
            encounter_id=values["encounter_id"],
        )
        cleaned_values["encounter_id"] = values["encounter_id"]

    if not cleaned_values:
        return build_document_detail_response(db=db, document=document)

    repository.update_document(
        db=db,
        document=document,
        data=cleaned_values,
    )
    record_document_audit(
        db=db,
        document=document,
        action="metadata_updated",
        status="updated",
        doctor_id=doctor.id,
    )
    db.commit()
    db.refresh(document)

    return build_document_detail_response(db=db, document=document)


def archive_document(
    db: Session,
    *,
    doctor: Doctor,
    patient_id: UUID,
    document_id: UUID,
) -> DocumentDetailResponse:
    document = get_owned_document_or_raise(
        db=db,
        doctor_id=doctor.id,
        patient_id=patient_id,
        document_id=document_id,
    )

    if document.is_active:
        repository.update_document(
            db=db,
            document=document,
            data={
                "is_active": False,
                "archived_at": utc_now(),
            },
        )
        record_document_audit(
            db=db,
            document=document,
            action="archived",
            status="archived",
            doctor_id=doctor.id,
        )
        db.commit()
        db.refresh(document)

    return build_document_detail_response(db=db, document=document)


def restore_document(
    db: Session,
    *,
    doctor: Doctor,
    patient_id: UUID,
    document_id: UUID,
) -> DocumentDetailResponse:
    document = get_owned_document_or_raise(
        db=db,
        doctor_id=doctor.id,
        patient_id=patient_id,
        document_id=document_id,
    )

    if not document.is_active:
        repository.update_document(
            db=db,
            document=document,
            data={
                "is_active": True,
                "archived_at": None,
            },
        )
        record_document_audit(
            db=db,
            document=document,
            action="restored",
            status="restored",
            doctor_id=doctor.id,
        )
        db.commit()
        db.refresh(document)

    return build_document_detail_response(db=db, document=document)


def create_document_signed_url(
    db: Session,
    *,
    doctor: Doctor,
    patient_id: UUID,
    document_id: UUID,
    storage_provider: StorageProvider,
    disposition: str,
) -> SignedDocumentUrlResponse:
    document = get_owned_document_or_raise(
        db=db,
        doctor_id=doctor.id,
        patient_id=patient_id,
        document_id=document_id,
    )
    ensure_document_can_be_read(document)
    signed_download = storage_provider.create_signed_download(
        object_path=document.storage_object_path,
    )
    record_document_audit(
        db=db,
        document=document,
        action=f"{disposition}_url_generated",
        status="created",
        doctor_id=doctor.id,
    )
    db.commit()

    return SignedDocumentUrlResponse(
        document_id=document.id,
        signed_url=signed_download.signed_url,
        expires_in=signed_download.expires_in,
        disposition=disposition,
    )


def process_document_now(
    db: Session,
    *,
    doctor: Doctor,
    patient_id: UUID,
    document_id: UUID,
    storage_provider: StorageProvider,
    force: bool,
):
    return document_job_dispatcher.run_now(
        db=db,
        doctor_id=doctor.id,
        patient_id=patient_id,
        document_id=document_id,
        storage_provider=storage_provider,
        force=force,
    )


def get_document_processing_status(
    db: Session,
    *,
    doctor: Doctor,
    patient_id: UUID,
    document_id: UUID,
) -> DocumentProcessingStatusResponse:
    document = get_owned_document_or_raise(
        db=db,
        doctor_id=doctor.id,
        patient_id=patient_id,
        document_id=document_id,
    )

    return DocumentProcessingStatusResponse(
        document=build_document_detail_response(db=db, document=document),
        jobs=repository.list_processing_jobs(db=db, document_id=document.id),
    )


def reconcile_patient_documents(
    db: Session,
    *,
    doctor: Doctor,
    patient_id: UUID,
    storage_provider: StorageProvider,
) -> DocumentReconciliationResponse:
    ensure_owned_patient(
        db=db,
        doctor_id=doctor.id,
        patient_id=patient_id,
    )
    documents = repository.list_owned_documents(
        db=db,
        doctor_id=doctor.id,
        patient_id=patient_id,
        offset=0,
        limit=1000,
        include_archived=True,
        document_type=None,
        processing_status=None,
        search=None,
    )
    issues: list[DocumentReconciliationIssue] = []

    for document in documents:
        if document.upload_status == "uploaded":
            try:
                exists = storage_provider.object_exists(
                    object_path=document.storage_object_path
                )
            except StorageProviderError:
                exists = False

            if not exists:
                issues.append(
                    DocumentReconciliationIssue(
                        document_id=document.id,
                        issue_type="missing_storage_object",
                        status="failed",
                        detail="Document metadata exists but the original object is missing.",
                    )
                )

        if document.verification_status == "verified" and document.size_bytes_actual is None:
            issues.append(
                DocumentReconciliationIssue(
                    document_id=document.id,
                    issue_type="missing_verified_size",
                    status="warning",
                    detail="Verified document is missing actual size metadata.",
                )
            )

        latest_job = repository.get_latest_processing_job(
            db=db,
            document_id=document.id,
        )

        if document.processing_status == "processing" and latest_job is None:
            issues.append(
                DocumentReconciliationIssue(
                    document_id=document.id,
                    issue_type="processing_without_job",
                    status="warning",
                    detail="Document is marked processing but no processing job exists.",
                )
            )

    return DocumentReconciliationResponse(
        issues=issues,
        total=len(issues),
    )


def get_document_text(db: Session, *, doctor: Doctor, patient_id: UUID, document_id: UUID):
    get_owned_document_or_raise(
        db=db,
        doctor_id=doctor.id,
        patient_id=patient_id,
        document_id=document_id,
    )

    return repository.get_document_text(db=db, document_id=document_id)


def list_document_pages(db: Session, *, doctor: Doctor, patient_id: UUID, document_id: UUID):
    get_owned_document_or_raise(
        db=db,
        doctor_id=doctor.id,
        patient_id=patient_id,
        document_id=document_id,
    )

    return repository.list_document_pages(db=db, document_id=document_id)


def list_document_sections(db: Session, *, doctor: Doctor, patient_id: UUID, document_id: UUID):
    get_owned_document_or_raise(
        db=db,
        doctor_id=doctor.id,
        patient_id=patient_id,
        document_id=document_id,
    )

    return repository.list_document_sections(db=db, document_id=document_id)


def list_document_artifacts(db: Session, *, doctor: Doctor, patient_id: UUID, document_id: UUID):
    get_owned_document_or_raise(
        db=db,
        doctor_id=doctor.id,
        patient_id=patient_id,
        document_id=document_id,
    )

    return repository.list_document_artifacts(db=db, document_id=document_id)


def list_document_audit_events(db: Session, *, doctor: Doctor, patient_id: UUID, document_id: UUID):
    get_owned_document_or_raise(
        db=db,
        doctor_id=doctor.id,
        patient_id=patient_id,
        document_id=document_id,
    )

    return repository.list_document_audit_events(db=db, document_id=document_id)


def ensure_owned_patient(db: Session, *, doctor_id: UUID, patient_id: UUID) -> None:
    patient = repository.get_owned_patient(
        db=db,
        doctor_id=doctor_id,
        patient_id=patient_id,
    )

    if patient is None:
        raise DocumentNotFound("Patient not found.")


def validate_owned_encounter(
    db: Session,
    *,
    doctor_id: UUID,
    patient_id: UUID,
    encounter_id: Optional[UUID],
) -> None:
    if encounter_id is None:
        return

    encounter = repository.get_owned_encounter(
        db=db,
        doctor_id=doctor_id,
        patient_id=patient_id,
        encounter_id=encounter_id,
    )

    if encounter is None:
        raise EncounterDocumentMismatch("Encounter does not belong to this patient.")


def get_owned_document_or_raise(
    db: Session,
    *,
    doctor_id: UUID,
    patient_id: UUID,
    document_id: UUID,
) -> Document:
    document = repository.get_owned_document(
        db=db,
        doctor_id=doctor_id,
        patient_id=patient_id,
        document_id=document_id,
    )

    if document is None:
        raise DocumentNotFound("Document not found.")

    return document


def download_uploaded_document(
    *,
    document: Document,
    storage_provider: StorageProvider,
) -> bytes:
    try:
        return storage_provider.download_bytes(
            object_path=document.storage_object_path,
            max_bytes=settings.document_max_file_size_bytes,
        )
    except StorageProviderError as error:
        raise DocumentObjectMissing("Uploaded document was not found in storage.") from error


def verify_uploaded_content(
    *,
    document: Document,
    content: bytes,
    checksum_override: Optional[str],
) -> None:
    if len(content) != document.size_bytes_expected:
        raise DocumentSizeMismatch("Uploaded file size does not match the expected size.")

    actual_checksum = sha256_hex(content)
    expected_checksum = normalize_sha256(checksum_override) or document.checksum_expected

    if expected_checksum and expected_checksum != actual_checksum:
        raise DocumentChecksumMismatch("Uploaded file checksum does not match.")

    signature = detect_file_signature(
        content=content,
        filename=document.original_filename,
        declared_content_type=document.declared_content_type,
    )

    if signature.content_type != document.declared_content_type:
        raise DocumentContentTypeMismatch("Uploaded file content type does not match.")

    document.detected_content_type = signature.content_type


def safe_get_metadata(
    *,
    storage_provider: StorageProvider,
    object_path: str,
):
    try:
        return storage_provider.get_object_metadata(object_path=object_path)
    except StorageProviderError:
        return None


def build_document_detail_response(
    *,
    db: Session,
    document: Document,
) -> DocumentDetailResponse:
    data = DocumentSummaryResponse.model_validate(document).model_dump()

    return DocumentDetailResponse(
        **data,
        page_count=repository.count_document_pages(db=db, document_id=document.id),
        section_count=repository.count_document_sections(db=db, document_id=document.id),
        artifact_count=repository.count_document_artifacts(db=db, document_id=document.id),
        extracted_text_available=repository.get_document_text(
            db=db,
            document_id=document.id,
        )
        is not None,
        replaces_document_id=document.replaces_document_id,
        superseded_by_document_id=document.superseded_by_document_id,
    )


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
