from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.doctor.model import Doctor
from app.evaluation.experiments.services import audit_service, experiment_service
from app.evaluation.judges.human_review.repositories import annotation_repository


def list_review_queue(db: Session, *, doctor: Doctor) -> list[dict]:
    queue = []

    for experiment in experiment_service.list_experiments(db, doctor=doctor):
        queue.extend(audit_service.list_hallucination_audit(db, experiment.id))

    return queue


def annotate_claim(db: Session, *, doctor: Doctor, claim_id: UUID, value: str, notes: Optional[str]) -> dict:
    claim = annotation_repository.get_owned_claim(db, claim_id=claim_id, doctor_id=doctor.id)

    if claim is None:
        raise ValueError("Review item not found.")

    annotation = annotation_repository.create_annotation(
        db,
        {
            "output_id": claim.output_id,
            "claim_id": claim.id,
            "reviewer_id": doctor.id,
            "annotation_type": "human_review",
            "value": value,
            "notes": notes,
        },
    )
    db.commit()
    db.refresh(annotation)
    return {
        "id": str(annotation.id),
        "claim_id": str(claim.id),
        "output_id": str(claim.output_id),
        "value": annotation.value,
        "notes": annotation.notes,
        "created_at": annotation.created_at.isoformat(),
    }
