from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.health.schemas import (
    DatabaseHealthResponse,
    LivenessResponse,
    StorageHealthResponse,
)
from app.health.service import check_database_connection
from app.storage.health import check_storage_readiness


router = APIRouter(
    prefix="/health",
    tags=["Health"],
)


@router.get(
    "/live",
    response_model=LivenessResponse,
)
def liveness() -> LivenessResponse:
    return LivenessResponse(status="healthy")


@router.get(
    "/database",
    response_model=DatabaseHealthResponse,
)
def database_health(
    db: Session = Depends(get_db),
) -> DatabaseHealthResponse:
    result = check_database_connection(db)

    return DatabaseHealthResponse(**result)


@router.get(
    "/storage",
    response_model=StorageHealthResponse,
)
def storage_health() -> StorageHealthResponse:
    result = check_storage_readiness()

    return StorageHealthResponse(**result.model_dump())
