from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.doctor.dependencies import CurrentDoctor
from app.evaluation.experiments.schemas.experiment import (
    ExperimentCreateRequest,
    ExperimentProgressResponse,
    ExperimentResponse,
)
from app.evaluation.experiments.services import experiment_service


router = APIRouter()
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.post("/api/evaluation/experiments", response_model=ExperimentResponse, status_code=status.HTTP_201_CREATED)
def create_evaluation_experiment(
    request: ExperimentCreateRequest,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
) -> ExperimentResponse:
    try:
        return experiment_service.create_experiment(db, doctor=current_doctor, request=request)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error


@router.get("/api/evaluation/experiments", response_model=list[ExperimentResponse])
def list_evaluation_experiments(current_doctor: CurrentDoctor, db: DatabaseSession) -> list[ExperimentResponse]:
    return experiment_service.list_experiments(db, doctor=current_doctor)


@router.get("/api/evaluation/experiments/{experiment_id}", response_model=ExperimentResponse)
def get_evaluation_experiment(experiment_id: UUID, current_doctor: CurrentDoctor, db: DatabaseSession) -> ExperimentResponse:
    try:
        return experiment_service.get_experiment(db, doctor=current_doctor, experiment_id=experiment_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post("/api/evaluation/experiments/{experiment_id}/start", response_model=ExperimentResponse)
def start_evaluation_experiment(experiment_id: UUID, current_doctor: CurrentDoctor, db: DatabaseSession) -> ExperimentResponse:
    try:
        return experiment_service.start_experiment(db, doctor=current_doctor, experiment_id=experiment_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post("/api/evaluation/experiments/{experiment_id}/cancel", response_model=ExperimentResponse)
def cancel_evaluation_experiment(experiment_id: UUID, current_doctor: CurrentDoctor, db: DatabaseSession) -> ExperimentResponse:
    try:
        return experiment_service.cancel_experiment(db, doctor=current_doctor, experiment_id=experiment_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post("/api/evaluation/experiments/{experiment_id}/resume", response_model=ExperimentResponse)
def resume_evaluation_experiment(experiment_id: UUID, current_doctor: CurrentDoctor, db: DatabaseSession) -> ExperimentResponse:
    try:
        return experiment_service.resume_experiment(db, doctor=current_doctor, experiment_id=experiment_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.get("/api/evaluation/experiments/{experiment_id}/progress", response_model=ExperimentProgressResponse)
def get_evaluation_experiment_progress(
    experiment_id: UUID,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
) -> ExperimentProgressResponse:
    try:
        return experiment_service.get_progress(db, doctor=current_doctor, experiment_id=experiment_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
