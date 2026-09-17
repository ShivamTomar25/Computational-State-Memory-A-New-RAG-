from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.doctor.dependencies import CurrentDoctor
from app.patient.exceptions import (
    InvalidPatientValueError,
    PatientCodeAlreadyExistsError,
    PatientNotFoundError,
)
from app.patient.schemas import PatientCreate, PatientListResponse, PatientResponse, PatientUpdate
from app.patient.service import (
    archive_patient,
    create_patient,
    get_patient,
    list_patients,
    restore_patient,
    update_patient,
)
from app.patient.workspace.schemas import PatientWorkspaceSummaryResponse
from app.patient.workspace.service import get_patient_workspace_summary


router = APIRouter(
    prefix="/api/patients",
    tags=["Patients"],
)


DatabaseSession = Annotated[Session, Depends(get_db)]


@router.post(
    "",
    response_model=PatientResponse,
    status_code=status.HTTP_201_CREATED,
)
def create(
    patient_data: PatientCreate,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
) -> PatientResponse:
    try:
        patient = create_patient(
            db=db,
            doctor=current_doctor,
            patient_data=patient_data,
        )

        return PatientResponse.model_validate(patient)

    except PatientCodeAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    except InvalidPatientValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error


@router.get(
    "",
    response_model=PatientListResponse,
)
def list_owned_patients(
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    search: Optional[str] = None,
    include_archived: bool = False,
) -> PatientListResponse:
    return list_patients(
        db=db,
        doctor=current_doctor,
        page=page,
        page_size=page_size,
        search=search,
        include_archived=include_archived,
    )


@router.get(
    "/{patient_id}/workspace-summary",
    response_model=PatientWorkspaceSummaryResponse,
)
def get_workspace_summary(
    patient_id: UUID,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
) -> PatientWorkspaceSummaryResponse:
    try:
        return get_patient_workspace_summary(
            db=db,
            doctor=current_doctor,
            patient_id=patient_id,
        )

    except PatientNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error


@router.get(
    "/{patient_id}",
    response_model=PatientResponse,
)
def get_one(
    patient_id: UUID,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
) -> PatientResponse:
    try:
        patient = get_patient(
            db=db,
            doctor=current_doctor,
            patient_id=patient_id,
        )

        return PatientResponse.model_validate(patient)

    except PatientNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error


@router.patch(
    "/{patient_id}",
    response_model=PatientResponse,
)
def update(
    patient_id: UUID,
    patient_data: PatientUpdate,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
) -> PatientResponse:
    try:
        patient = update_patient(
            db=db,
            doctor=current_doctor,
            patient_id=patient_id,
            patient_data=patient_data,
        )

        return PatientResponse.model_validate(patient)

    except PatientNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    except PatientCodeAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    except InvalidPatientValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error


@router.post(
    "/{patient_id}/archive",
    response_model=PatientResponse,
)
def archive(
    patient_id: UUID,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
) -> PatientResponse:
    try:
        patient = archive_patient(
            db=db,
            doctor=current_doctor,
            patient_id=patient_id,
        )

        return PatientResponse.model_validate(patient)

    except PatientNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    except InvalidPatientValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error


@router.post(
    "/{patient_id}/restore",
    response_model=PatientResponse,
)
def restore(
    patient_id: UUID,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
) -> PatientResponse:
    try:
        patient = restore_patient(
            db=db,
            doctor=current_doctor,
            patient_id=patient_id,
        )

        return PatientResponse.model_validate(patient)

    except PatientNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    except InvalidPatientValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
