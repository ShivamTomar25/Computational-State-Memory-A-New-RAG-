from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.doctor.dependencies import CurrentDoctor
from app.evaluation.experiments.services import audit_service
from app.evaluation.experiments.services import experiment_service


router = APIRouter()
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("/api/evaluation/experiments/{experiment_id}/results")
def get_evaluation_results(experiment_id: UUID, current_doctor: CurrentDoctor, db: DatabaseSession):
    try:
        return experiment_service.get_results(db, doctor=current_doctor, experiment_id=experiment_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.get("/api/evaluation/experiments/{experiment_id}/rankings")
def get_evaluation_rankings(experiment_id: UUID, current_doctor: CurrentDoctor, db: DatabaseSession):
    return get_evaluation_results(experiment_id, current_doctor, db).rankings


@router.get("/api/evaluation/experiments/{experiment_id}/matrix")
def get_evaluation_matrix(experiment_id: UUID, current_doctor: CurrentDoctor, db: DatabaseSession):
    results = get_evaluation_results(experiment_id, current_doctor, db).metric_results
    matrix = {}

    for result in results:
        system_type = result["details"].get("system_type", "unknown")
        matrix.setdefault(system_type, {})[result["metric_name"]] = {
            "value": result["value"],
            "status": result["details"].get("status", "pending"),
            "applicable": result["applicable"],
            "reason_not_applicable": result["reason_not_applicable"],
            "numerator": result["numerator"],
            "denominator": result["denominator"],
        }

    return matrix


@router.get("/api/evaluation/experiments/{experiment_id}/statistics")
def get_evaluation_statistics(experiment_id: UUID, current_doctor: CurrentDoctor, db: DatabaseSession):
    return get_evaluation_results(experiment_id, current_doctor, db).statistics


@router.get("/api/evaluation/experiments/{experiment_id}/metrics/{metric_name}")
def get_evaluation_metric(experiment_id: UUID, metric_name: str, current_doctor: CurrentDoctor, db: DatabaseSession):
    results = get_evaluation_results(experiment_id, current_doctor, db).metric_results
    return [result for result in results if result["metric_name"] == metric_name]


@router.get("/api/evaluation/experiments/{experiment_id}/systems/{system_type}")
def get_evaluation_system(experiment_id: UUID, system_type: str, current_doctor: CurrentDoctor, db: DatabaseSession):
    results = get_evaluation_results(experiment_id, current_doctor, db).metric_results
    return [result for result in results if result["details"].get("system_type") == system_type]


@router.get("/api/evaluation/experiments/{experiment_id}/cases/{case_id}")
def get_evaluation_case(experiment_id: UUID, case_id: UUID, current_doctor: CurrentDoctor, db: DatabaseSession):
    results = get_evaluation_results(experiment_id, current_doctor, db).metric_results
    case_results = [result for result in results if result["details"].get("case_id") == str(case_id)]

    return {
        "experiment_id": str(experiment_id),
        "case_id": str(case_id),
        "metric_results": case_results,
    }


@router.get("/api/evaluation/experiments/{experiment_id}/claims")
def get_evaluation_claims(experiment_id: UUID, current_doctor: CurrentDoctor, db: DatabaseSession):
    get_evaluation_results(experiment_id, current_doctor, db)
    return audit_service.list_claim_audit(db, experiment_id)


@router.get("/api/evaluation/experiments/{experiment_id}/citations")
def get_evaluation_citations(experiment_id: UUID, current_doctor: CurrentDoctor, db: DatabaseSession):
    get_evaluation_results(experiment_id, current_doctor, db)
    return audit_service.list_citation_audit(db, experiment_id)


@router.get("/api/evaluation/experiments/{experiment_id}/hallucinations")
def get_evaluation_hallucinations(experiment_id: UUID, current_doctor: CurrentDoctor, db: DatabaseSession):
    get_evaluation_results(experiment_id, current_doctor, db)
    return audit_service.list_hallucination_audit(db, experiment_id)
