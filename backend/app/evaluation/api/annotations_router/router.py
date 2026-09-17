from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.doctor.dependencies import CurrentDoctor
from app.evaluation.judges.human_review import service as human_review_service


router = APIRouter()
DatabaseSession = Annotated[Session, Depends(get_db)]


class AnnotationRequest(BaseModel):
    value: str
    notes: Optional[str] = None


@router.get("/api/evaluation/review-queue")
def get_review_queue(current_doctor: CurrentDoctor, db: DatabaseSession):
    return human_review_service.list_review_queue(db, doctor=current_doctor)


@router.post("/api/evaluation/review-queue/{item_id}/annotate")
def annotate_review_item(item_id: UUID, request: AnnotationRequest, current_doctor: CurrentDoctor, db: DatabaseSession):
    try:
        return human_review_service.annotate_claim(
            db,
            doctor=current_doctor,
            claim_id=item_id,
            value=request.value,
            notes=request.notes,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
