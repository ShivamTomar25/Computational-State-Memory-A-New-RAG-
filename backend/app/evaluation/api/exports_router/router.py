from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.doctor.dependencies import CurrentDoctor
from app.evaluation.exports.services import export_service
from app.evaluation.experiments.services import experiment_service


router = APIRouter()
DatabaseSession = Annotated[Session, Depends(get_db)]


class ExportRequest(BaseModel):
    export_type: str


@router.post("/api/evaluation/experiments/{experiment_id}/exports")
def create_evaluation_export(experiment_id: UUID, request: ExportRequest, current_doctor: CurrentDoctor, db: DatabaseSession):
    results = experiment_service.get_results(db, doctor=current_doctor, experiment_id=experiment_id)
    return export_service.create_inline_export(
        db,
        experiment_id=experiment_id,
        export_type=request.export_type,
        content=results.model_dump(mode="json"),
    )


@router.get("/api/evaluation/experiments/{experiment_id}/exports")
def list_evaluation_exports(experiment_id: UUID, current_doctor: CurrentDoctor, db: DatabaseSession):
    experiment_service.get_results(db, doctor=current_doctor, experiment_id=experiment_id)
    return export_service.list_experiment_exports(db, experiment_id=experiment_id)
