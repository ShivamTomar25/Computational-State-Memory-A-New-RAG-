from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.document import repository
from app.document.models import Document, DocumentAuditEvent


def record_document_audit(
    db: Session,
    *,
    document: Document,
    action: str,
    status: str,
    doctor_id: Optional[UUID],
    actor_type: str = "doctor",
    metadata: Optional[dict] = None,
) -> DocumentAuditEvent:
    return repository.create_audit_event(
        db=db,
        document=document,
        action=action,
        status=status,
        doctor_id=doctor_id,
        actor_type=actor_type,
        metadata=metadata,
    )
