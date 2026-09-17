from __future__ import annotations

from datetime import date
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.doctor.dependencies import CurrentDoctor
from app.document.exceptions import (
    DocumentAlreadyUploaded,
    DocumentChecksumMismatch,
    DocumentContentTypeMismatch,
    DocumentError,
    DocumentInactive,
    DocumentNotFound,
    DocumentNotUploaded,
    DocumentNotVerified,
    DocumentObjectMissing,
    DocumentSizeMismatch,
    DocumentUploadExpired,
    EncounterDocumentMismatch,
    InvalidDocumentDate,
    InvalidDocumentType,
    ProcessingNotAllowed,
)
from app.document.schemas import (
    DocumentArtifactResponse,
    DocumentAuditEventResponse,
    DocumentDetailResponse,
    DocumentDirectUploadResponse,
    DocumentListResponse,
    DocumentPageResponse,
    DocumentProcessingJobResponse,
    DocumentProcessingRequest,
    DocumentProcessingStatusResponse,
    DocumentReconciliationResponse,
    DocumentSectionResponse,
    DocumentTextResponse,
    DocumentUpdate,
    DocumentUploadCompleteRequest,
    DocumentUploadInitiateRequest,
    DocumentUploadInitiateResponse,
    SignedDocumentUrlResponse,
)
from app.document.service import (
    archive_document,
    complete_document_upload,
    create_document_signed_url,
    direct_upload_document,
    get_document_detail,
    get_document_processing_status,
    get_document_text,
    initiate_document_upload,
    list_document_artifacts,
    list_document_audit_events,
    list_document_pages,
    list_document_sections,
    list_documents,
    process_document_now,
    reconcile_patient_documents,
    restore_document,
    update_document_metadata,
)
from app.storage.dependencies import get_storage_provider
from app.storage.exceptions import (
    StorageEmptyFile,
    StorageFileTooLarge,
    StorageInvalidFilename,
    StorageProviderError,
    StorageUnsupportedContentType,
)
from app.storage.interface import StorageProvider


router = APIRouter(
    prefix="/api/patients/{patient_id}/documents",
    tags=["Documents"],
)


DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentStorageProvider = Annotated[StorageProvider, Depends(get_storage_provider)]


@router.post(
    "/upload/initiate",
    response_model=DocumentUploadInitiateResponse,
    status_code=status.HTTP_201_CREATED,
)
def initiate_upload(
    patient_id: UUID,
    upload_data: DocumentUploadInitiateRequest,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
    storage_provider: CurrentStorageProvider,
) -> DocumentUploadInitiateResponse:
    try:
        return initiate_document_upload(
            db=db,
            doctor=current_doctor,
            patient_id=patient_id,
            upload_data=upload_data,
            storage_provider=storage_provider,
        )
    except Exception as error:
        raise_document_http_error(error)


@router.post(
    "/upload/direct",
    response_model=DocumentDirectUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def direct_upload(
    patient_id: UUID,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
    storage_provider: CurrentStorageProvider,
    file: UploadFile = File(...),
    document_type: str = Form("other"),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    document_date: Optional[date] = Form(None),
    encounter_id: Optional[UUID] = Form(None),
) -> DocumentDirectUploadResponse:
    try:
        content = await file.read()

        return direct_upload_document(
            db=db,
            doctor=current_doctor,
            patient_id=patient_id,
            original_filename=file.filename or "document",
            content_type=file.content_type or "application/octet-stream",
            content=content,
            document_type=document_type,
            title=title,
            description=description,
            document_date=document_date,
            encounter_id=encounter_id,
            storage_provider=storage_provider,
        )
    except Exception as error:
        raise_document_http_error(error)


@router.get(
    "",
    response_model=DocumentListResponse,
)
def list_patient_documents(
    patient_id: UUID,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    include_archived: bool = False,
    document_type: Optional[str] = None,
    processing_status: Optional[str] = None,
    search: Optional[str] = None,
) -> DocumentListResponse:
    try:
        return list_documents(
            db=db,
            doctor=current_doctor,
            patient_id=patient_id,
            page=page,
            page_size=page_size,
            include_archived=include_archived,
            document_type=document_type,
            processing_status=processing_status,
            search=search,
        )
    except Exception as error:
        raise_document_http_error(error)


@router.get(
    "/reconcile",
    response_model=DocumentReconciliationResponse,
)
def reconcile_documents(
    patient_id: UUID,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
    storage_provider: CurrentStorageProvider,
) -> DocumentReconciliationResponse:
    try:
        return reconcile_patient_documents(
            db=db,
            doctor=current_doctor,
            patient_id=patient_id,
            storage_provider=storage_provider,
        )
    except Exception as error:
        raise_document_http_error(error)


@router.get(
    "/{document_id}",
    response_model=DocumentDetailResponse,
)
def get_one_document(
    patient_id: UUID,
    document_id: UUID,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
) -> DocumentDetailResponse:
    try:
        return get_document_detail(
            db=db,
            doctor=current_doctor,
            patient_id=patient_id,
            document_id=document_id,
        )
    except Exception as error:
        raise_document_http_error(error)


@router.patch(
    "/{document_id}",
    response_model=DocumentDetailResponse,
)
def update_document(
    patient_id: UUID,
    document_id: UUID,
    update_data: DocumentUpdate,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
) -> DocumentDetailResponse:
    try:
        return update_document_metadata(
            db=db,
            doctor=current_doctor,
            patient_id=patient_id,
            document_id=document_id,
            update_data=update_data,
        )
    except Exception as error:
        raise_document_http_error(error)


@router.post(
    "/{document_id}/complete",
    response_model=DocumentDetailResponse,
)
def complete_upload(
    patient_id: UUID,
    document_id: UUID,
    completion_data: DocumentUploadCompleteRequest,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
    storage_provider: CurrentStorageProvider,
) -> DocumentDetailResponse:
    try:
        return complete_document_upload(
            db=db,
            doctor=current_doctor,
            patient_id=patient_id,
            document_id=document_id,
            completion_data=completion_data,
            storage_provider=storage_provider,
        )
    except Exception as error:
        raise_document_http_error(error)


@router.post(
    "/{document_id}/archive",
    response_model=DocumentDetailResponse,
)
def archive(
    patient_id: UUID,
    document_id: UUID,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
) -> DocumentDetailResponse:
    try:
        return archive_document(
            db=db,
            doctor=current_doctor,
            patient_id=patient_id,
            document_id=document_id,
        )
    except Exception as error:
        raise_document_http_error(error)


@router.post(
    "/{document_id}/restore",
    response_model=DocumentDetailResponse,
)
def restore(
    patient_id: UUID,
    document_id: UUID,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
) -> DocumentDetailResponse:
    try:
        return restore_document(
            db=db,
            doctor=current_doctor,
            patient_id=patient_id,
            document_id=document_id,
        )
    except Exception as error:
        raise_document_http_error(error)


@router.post(
    "/{document_id}/view-url",
    response_model=SignedDocumentUrlResponse,
)
def view_url(
    patient_id: UUID,
    document_id: UUID,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
    storage_provider: CurrentStorageProvider,
) -> SignedDocumentUrlResponse:
    try:
        return create_document_signed_url(
            db=db,
            doctor=current_doctor,
            patient_id=patient_id,
            document_id=document_id,
            storage_provider=storage_provider,
            disposition="view",
        )
    except Exception as error:
        raise_document_http_error(error)


@router.post(
    "/{document_id}/download-url",
    response_model=SignedDocumentUrlResponse,
)
def download_url(
    patient_id: UUID,
    document_id: UUID,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
    storage_provider: CurrentStorageProvider,
) -> SignedDocumentUrlResponse:
    try:
        return create_document_signed_url(
            db=db,
            doctor=current_doctor,
            patient_id=patient_id,
            document_id=document_id,
            storage_provider=storage_provider,
            disposition="download",
        )
    except Exception as error:
        raise_document_http_error(error)


@router.post(
    "/{document_id}/process",
    response_model=DocumentProcessingJobResponse,
)
def process_now(
    patient_id: UUID,
    document_id: UUID,
    request_data: DocumentProcessingRequest,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
    storage_provider: CurrentStorageProvider,
) -> DocumentProcessingJobResponse:
    try:
        job = process_document_now(
            db=db,
            doctor=current_doctor,
            patient_id=patient_id,
            document_id=document_id,
            storage_provider=storage_provider,
            force=request_data.force,
        )

        return DocumentProcessingJobResponse.model_validate(job)
    except Exception as error:
        raise_document_http_error(error)


@router.get(
    "/{document_id}/processing",
    response_model=DocumentProcessingStatusResponse,
)
def processing_status(
    patient_id: UUID,
    document_id: UUID,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
) -> DocumentProcessingStatusResponse:
    try:
        return get_document_processing_status(
            db=db,
            doctor=current_doctor,
            patient_id=patient_id,
            document_id=document_id,
        )
    except Exception as error:
        raise_document_http_error(error)


@router.get(
    "/{document_id}/text",
    response_model=Optional[DocumentTextResponse],
)
def document_text(
    patient_id: UUID,
    document_id: UUID,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
):
    try:
        text = get_document_text(
            db=db,
            doctor=current_doctor,
            patient_id=patient_id,
            document_id=document_id,
        )

        return DocumentTextResponse.model_validate(text) if text else None
    except Exception as error:
        raise_document_http_error(error)


@router.get(
    "/{document_id}/pages",
    response_model=list[DocumentPageResponse],
)
def document_pages(
    patient_id: UUID,
    document_id: UUID,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
) -> list[DocumentPageResponse]:
    try:
        return [
            DocumentPageResponse.model_validate(page)
            for page in list_document_pages(
                db=db,
                doctor=current_doctor,
                patient_id=patient_id,
                document_id=document_id,
            )
        ]
    except Exception as error:
        raise_document_http_error(error)


@router.get(
    "/{document_id}/sections",
    response_model=list[DocumentSectionResponse],
)
def document_sections(
    patient_id: UUID,
    document_id: UUID,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
) -> list[DocumentSectionResponse]:
    try:
        return [
            DocumentSectionResponse.model_validate(section)
            for section in list_document_sections(
                db=db,
                doctor=current_doctor,
                patient_id=patient_id,
                document_id=document_id,
            )
        ]
    except Exception as error:
        raise_document_http_error(error)


@router.get(
    "/{document_id}/artifacts",
    response_model=list[DocumentArtifactResponse],
)
def document_artifacts(
    patient_id: UUID,
    document_id: UUID,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
) -> list[DocumentArtifactResponse]:
    try:
        return [
            DocumentArtifactResponse.model_validate(artifact)
            for artifact in list_document_artifacts(
                db=db,
                doctor=current_doctor,
                patient_id=patient_id,
                document_id=document_id,
            )
        ]
    except Exception as error:
        raise_document_http_error(error)


@router.get(
    "/{document_id}/audit",
    response_model=list[DocumentAuditEventResponse],
)
def document_audit(
    patient_id: UUID,
    document_id: UUID,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
) -> list[DocumentAuditEventResponse]:
    try:
        return [
            DocumentAuditEventResponse.model_validate(event)
            for event in list_document_audit_events(
                db=db,
                doctor=current_doctor,
                patient_id=patient_id,
                document_id=document_id,
            )
        ]
    except Exception as error:
        raise_document_http_error(error)


def raise_document_http_error(error: Exception):
    if isinstance(error, HTTPException):
        raise error

    if isinstance(error, DocumentNotFound):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    if isinstance(error, DocumentObjectMissing):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    if isinstance(error, (DocumentNotUploaded, DocumentNotVerified, DocumentInactive)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    if isinstance(error, (DocumentUploadExpired, DocumentAlreadyUploaded, ProcessingNotAllowed)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    if isinstance(
        error,
        (
            InvalidDocumentType,
            InvalidDocumentDate,
            EncounterDocumentMismatch,
            DocumentSizeMismatch,
            DocumentChecksumMismatch,
            DocumentContentTypeMismatch,
            StorageInvalidFilename,
            StorageUnsupportedContentType,
            StorageFileTooLarge,
            StorageEmptyFile,
            ValueError,
        ),
    ):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error

    if isinstance(error, StorageProviderError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Storage provider request failed.",
        ) from error

    if isinstance(error, DocumentError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Document request failed.",
    ) from error
