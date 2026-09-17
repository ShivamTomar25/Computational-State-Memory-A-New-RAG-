from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.doctor.dependencies import CurrentDoctor
from app.doctor.exceptions import (
    DoctorEmailAlreadyExistsError,
    DoctorLicenseAlreadyExistsError,
    InactiveDoctorError,
    InvalidDoctorCredentialsError,
)
from app.doctor.schemas import (
    AccessTokenResponse,
    DoctorCreate,
    DoctorLogin,
    DoctorResponse,
    DoctorUpdate,
)
from app.doctor.service import (
    authenticate_doctor,
    register_doctor,
    update_doctor_profile,
)
from app.security.token import create_access_token


router = APIRouter(
    prefix="/api/doctors",
    tags=["Doctors"],
)


DatabaseSession = Annotated[Session, Depends(get_db)]


@router.post(
    "/register",
    response_model=DoctorResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    doctor_data: DoctorCreate,
    db: DatabaseSession,
) -> DoctorResponse:
    try:
        doctor = register_doctor(
            db=db,
            doctor_data=doctor_data,
        )

        return DoctorResponse.model_validate(doctor)

    except (
        DoctorEmailAlreadyExistsError,
        DoctorLicenseAlreadyExistsError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.post(
    "/login",
    response_model=AccessTokenResponse,
)
def login(
    login_data: DoctorLogin,
    db: DatabaseSession,
) -> AccessTokenResponse:
    try:
        doctor = authenticate_doctor(
            db=db,
            login_data=login_data,
        )

        access_token = create_access_token(doctor_id=doctor.id)

        return AccessTokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in_seconds=settings.access_token_expire_minutes * 60,
            doctor=DoctorResponse.model_validate(doctor),
        )

    except InvalidDoctorCredentialsError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
            headers={
                "WWW-Authenticate": "Bearer",
            },
        ) from error

    except InactiveDoctorError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error


@router.get(
    "/me",
    response_model=DoctorResponse,
)
def get_my_profile(
    current_doctor: CurrentDoctor,
) -> DoctorResponse:
    return DoctorResponse.model_validate(current_doctor)


@router.patch(
    "/me",
    response_model=DoctorResponse,
)
def update_my_profile(
    doctor_data: DoctorUpdate,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
) -> DoctorResponse:
    try:
        updated_doctor = update_doctor_profile(
            db=db,
            doctor=current_doctor,
            doctor_data=doctor_data,
        )

        return DoctorResponse.model_validate(updated_doctor)

    except DoctorLicenseAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
