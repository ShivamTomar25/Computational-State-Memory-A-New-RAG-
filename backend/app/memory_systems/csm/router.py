from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.doctor.dependencies import CurrentDoctor
from app.memory_systems.common.schemas.memory import (
    MemoryIngestionRunResponse,
    MemoryInitializeResponse,
    MemoryRebuildRequest,
    MemorySyncRequest,
)
from app.memory_systems.csm.schemas import (
    CsmEvidenceResponse,
    CsmOverviewResponse,
    CsmReviewDecisionRequest,
    CsmReviewResponse,
)
from app.memory_systems.csm.service import (
    approve_review,
    get_csm_evidence,
    get_csm_evidence_item,
    get_csm_overview,
    initialize_csm,
    rebuild_csm,
    reject_review,
    sync_csm,
)


router = APIRouter(prefix="/api/patients/{patient_id}/csm", tags=["CSM"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=CsmOverviewResponse)
def get_patient_csm(patient_id: UUID, current_doctor: CurrentDoctor, db: DatabaseSession) -> CsmOverviewResponse:
    try:
        return get_csm_overview(db=db, doctor=current_doctor, patient_id=patient_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.get("/states")
def get_patient_csm_states(patient_id: UUID, current_doctor: CurrentDoctor, db: DatabaseSession):
    return get_patient_csm(patient_id, current_doctor, db).states


@router.get("/conflicts")
def get_patient_csm_conflicts(patient_id: UUID, current_doctor: CurrentDoctor, db: DatabaseSession):
    return get_patient_csm(patient_id, current_doctor, db).conflicts


@router.get("/evidence", response_model=list[CsmEvidenceResponse])
def get_patient_csm_evidence(patient_id: UUID, current_doctor: CurrentDoctor, db: DatabaseSession) -> list[CsmEvidenceResponse]:
    try:
        return get_csm_evidence(db=db, doctor=current_doctor, patient_id=patient_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.get("/evidence/{evidence_id}", response_model=CsmEvidenceResponse)
def get_patient_csm_evidence_item(
    patient_id: UUID,
    evidence_id: UUID,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
) -> CsmEvidenceResponse:
    try:
        return get_csm_evidence_item(
            db=db,
            doctor=current_doctor,
            patient_id=patient_id,
            evidence_id=evidence_id,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.get("/reviews", response_model=list[CsmReviewResponse])
def get_patient_csm_reviews(patient_id: UUID, current_doctor: CurrentDoctor, db: DatabaseSession) -> list[CsmReviewResponse]:
    return get_patient_csm(patient_id, current_doctor, db).reviews


@router.post("/initialize", response_model=MemoryInitializeResponse)
def initialize_patient_csm(patient_id: UUID, current_doctor: CurrentDoctor, db: DatabaseSession) -> MemoryInitializeResponse:
    try:
        return initialize_csm(db=db, doctor=current_doctor, patient_id=patient_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post("/sync", response_model=MemoryIngestionRunResponse)
def sync_patient_csm(
    patient_id: UUID,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
    request: Optional[MemorySyncRequest] = None,
) -> MemoryIngestionRunResponse:
    try:
        return sync_csm(db=db, doctor=current_doctor, patient_id=patient_id, request=request)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error


@router.post("/rebuild", response_model=MemoryIngestionRunResponse)
def rebuild_patient_csm(
    patient_id: UUID,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
    request: Optional[MemoryRebuildRequest] = None,
) -> MemoryIngestionRunResponse:
    try:
        return rebuild_csm(db=db, doctor=current_doctor, patient_id=patient_id, request=request)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error


@router.post("/reviews/{review_id}/approve", response_model=CsmReviewResponse)
def approve_patient_csm_review(
    patient_id: UUID,
    review_id: UUID,
    request: CsmReviewDecisionRequest,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
) -> CsmReviewResponse:
    try:
        return approve_review(db=db, doctor=current_doctor, patient_id=patient_id, review_id=review_id, note=request.note)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post("/reviews/{review_id}/reject", response_model=CsmReviewResponse)
def reject_patient_csm_review(
    patient_id: UUID,
    review_id: UUID,
    request: CsmReviewDecisionRequest,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
) -> CsmReviewResponse:
    try:
        return reject_review(db=db, doctor=current_doctor, patient_id=patient_id, review_id=review_id, note=request.note)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
