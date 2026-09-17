from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.document.models import DocumentProcessingJob
from app.document_processing.orchestration import process_owned_document
from app.storage.interface import StorageProvider


class LocalDocumentJobDispatcher:
    def run_now(
        self,
        db: Session,
        *,
        doctor_id: UUID,
        patient_id: UUID,
        document_id: UUID,
        storage_provider: StorageProvider,
        force: bool = False,
    ) -> DocumentProcessingJob:
        return process_owned_document(
            db=db,
            doctor_id=doctor_id,
            patient_id=patient_id,
            document_id=document_id,
            storage_provider=storage_provider,
            force=force,
        )


document_job_dispatcher = LocalDocumentJobDispatcher()
