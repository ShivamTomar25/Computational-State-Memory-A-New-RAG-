from __future__ import annotations

from datetime import datetime, timezone

from app.document.exceptions import (
    DocumentAlreadyUploaded,
    DocumentInactive,
    DocumentNotUploaded,
    DocumentNotVerified,
    DocumentUploadExpired,
    InvalidDocumentStatusTransition,
    ProcessingNotAllowed,
)
from app.document.models import Document


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_upload_can_complete(document: Document) -> None:
    if document.upload_status in {"uploaded", "cancelled"}:
        raise DocumentAlreadyUploaded("Document upload is already closed.")

    if document.upload_status == "expired":
        raise DocumentUploadExpired("Document upload has expired.")

    if document.upload_deadline_at < utc_now():
        raise DocumentUploadExpired("Document upload deadline has passed.")


def ensure_document_can_be_read(document: Document) -> None:
    if not document.is_active:
        raise DocumentInactive("Document is archived.")

    if document.upload_status != "uploaded":
        raise DocumentNotUploaded("Document has not been uploaded.")

    if document.verification_status != "verified":
        raise DocumentNotVerified("Document has not been verified.")


def ensure_metadata_can_change(document: Document) -> None:
    if not document.is_active:
        raise DocumentInactive("Archived documents cannot be changed.")

    if document.upload_status not in {"pending_upload", "uploaded"}:
        raise InvalidDocumentStatusTransition("Document cannot be changed in this state.")


def ensure_processing_can_start(document: Document) -> None:
    ensure_document_can_be_read(document)

    if document.processing_status in {"queued", "processing"}:
        raise ProcessingNotAllowed("Document processing is already running.")
