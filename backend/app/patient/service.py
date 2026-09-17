from datetime import date
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.doctor.model import Doctor
from app.patient import repository
from app.patient.exceptions import (
    InvalidPatientValueError,
    PatientCodeAlreadyExistsError,
    PatientNotFoundError,
)
from app.patient.model import Patient
from app.patient.schemas import PatientCreate, PatientListResponse, PatientResponse, PatientUpdate
from app.performance.caching.invalidation import invalidate_doctor, invalidate_patient


VALID_SEX_VALUES = {"female", "male", "other", "unknown"}


def create_patient(
    db: Session,
    *,
    doctor: Doctor,
    patient_data: PatientCreate,
) -> Patient:
    data = normalize_patient_create(patient_data)

    existing_patient = repository.get_patient_by_code(
        db=db,
        doctor_id=doctor.id,
        patient_code=data["patient_code"],
    )

    if existing_patient is not None:
        raise PatientCodeAlreadyExistsError(
            "A patient with this patient code already exists."
        )

    try:
        patient = repository.create_patient(
            db=db,
            doctor_id=doctor.id,
            **data,
        )

        db.commit()
        db.refresh(patient)
        initialize_patient_memory_systems(
            db=db,
            patient_id=patient.id,
        )
        db.refresh(patient)
        invalidate_doctor(doctor.id)
        invalidate_patient(patient.id)

        return patient

    except IntegrityError as error:
        db.rollback()

        raise PatientCodeAlreadyExistsError(
            "A patient with this patient code already exists."
        ) from error


def list_patients(
    db: Session,
    *,
    doctor: Doctor,
    page: int,
    page_size: int,
    search: Optional[str],
    include_archived: bool,
) -> PatientListResponse:
    normalized_search = normalize_search(search)
    offset = (page - 1) * page_size

    total = repository.count_patients(
        db=db,
        doctor_id=doctor.id,
        search=normalized_search,
        include_archived=include_archived,
    )
    patients = repository.list_patients(
        db=db,
        doctor_id=doctor.id,
        offset=offset,
        limit=page_size,
        search=normalized_search,
        include_archived=include_archived,
    )
    total_pages = (total + page_size - 1) // page_size if total else 0

    return PatientListResponse(
        items=[PatientResponse.model_validate(patient) for patient in patients],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


def get_patient(
    db: Session,
    *,
    doctor: Doctor,
    patient_id: UUID,
) -> Patient:
    patient = repository.get_patient_by_id(
        db=db,
        doctor_id=doctor.id,
        patient_id=patient_id,
    )

    if patient is None:
        raise PatientNotFoundError("Patient not found.")

    return patient


def update_patient(
    db: Session,
    *,
    doctor: Doctor,
    patient_id: UUID,
    patient_data: PatientUpdate,
) -> Patient:
    patient = get_patient(
        db=db,
        doctor=doctor,
        patient_id=patient_id,
    )
    update_data = normalize_patient_update(patient_data)

    if not update_data:
        return patient

    if "patient_code" in update_data:
        existing_patient = repository.get_patient_by_code(
            db=db,
            doctor_id=doctor.id,
            patient_code=update_data["patient_code"],
        )

        if existing_patient is not None and existing_patient.id != patient.id:
            raise PatientCodeAlreadyExistsError(
                "A patient with this patient code already exists."
            )

    try:
        updated_patient = repository.update_patient(
            db=db,
            patient=patient,
            update_data=update_data,
        )

        db.commit()
        db.refresh(updated_patient)
        invalidate_doctor(doctor.id)
        invalidate_patient(updated_patient.id)

        return updated_patient

    except IntegrityError as error:
        db.rollback()

        raise PatientCodeAlreadyExistsError(
            "A patient with this patient code already exists."
        ) from error


def archive_patient(
    db: Session,
    *,
    doctor: Doctor,
    patient_id: UUID,
) -> Patient:
    patient = get_patient(
        db=db,
        doctor=doctor,
        patient_id=patient_id,
    )

    if not patient.is_active:
        return patient

    updated_patient = change_patient_status(
        db=db,
        patient=patient,
        is_active=False,
    )
    invalidate_doctor(doctor.id)

    return updated_patient


def restore_patient(
    db: Session,
    *,
    doctor: Doctor,
    patient_id: UUID,
) -> Patient:
    patient = get_patient(
        db=db,
        doctor=doctor,
        patient_id=patient_id,
    )

    if patient.is_active:
        return patient

    updated_patient = change_patient_status(
        db=db,
        patient=patient,
        is_active=True,
    )
    invalidate_doctor(doctor.id)

    return updated_patient


def change_patient_status(
    db: Session,
    *,
    patient: Patient,
    is_active: bool,
) -> Patient:
    try:
        updated_patient = repository.set_patient_active(
            db=db,
            patient=patient,
            is_active=is_active,
        )

        db.commit()
        db.refresh(updated_patient)
        invalidate_patient(updated_patient.id)

        return updated_patient

    except IntegrityError as error:
        db.rollback()

        raise InvalidPatientValueError("Unable to update patient status.") from error


def initialize_patient_memory_systems(
    db: Session,
    *,
    patient_id: UUID,
) -> None:
    from app.memory_systems.common.services.memory_service import initialize_missing_system_instances

    initialize_missing_system_instances(
        db=db,
        patient_id=patient_id,
    )


def normalize_patient_create(patient_data: PatientCreate) -> dict[str, Any]:
    return normalize_patient_values(
        patient_data.model_dump(),
        partial=False,
    )


def normalize_patient_update(patient_data: PatientUpdate) -> dict[str, Any]:
    return normalize_patient_values(
        patient_data.model_dump(exclude_unset=True),
        partial=True,
    )


def normalize_patient_values(
    values: dict[str, Any],
    *,
    partial: bool,
) -> dict[str, Any]:
    normalized: dict[str, Any] = {}

    if "patient_code" in values:
        normalized["patient_code"] = normalize_patient_code(values["patient_code"])
    elif not partial:
        raise InvalidPatientValueError("Patient code is required.")

    if "full_name" in values:
        normalized["full_name"] = normalize_full_name(values["full_name"])
    elif not partial:
        raise InvalidPatientValueError("Full name is required.")

    if "date_of_birth" in values:
        normalized["date_of_birth"] = validate_date_of_birth(values["date_of_birth"])

    if "sex" in values:
        normalized["sex"] = normalize_sex(values["sex"])

    for field in (
        "phone",
        "address",
        "emergency_contact_name",
        "emergency_contact_phone",
    ):
        if field in values:
            normalized[field] = clean_optional_string(values[field])

    if "email" in values:
        normalized["email"] = normalize_email(values["email"])

    return normalized


def normalize_patient_code(value: str) -> str:
    cleaned_value = value.strip().upper()

    if not cleaned_value:
        raise InvalidPatientValueError("Patient code cannot be blank.")

    return cleaned_value


def normalize_full_name(value: str) -> str:
    cleaned_value = value.strip()

    if not cleaned_value:
        raise InvalidPatientValueError("Full name cannot be blank.")

    return cleaned_value


def validate_date_of_birth(value: Optional[date]) -> Optional[date]:
    if value is not None and value > date.today():
        raise InvalidPatientValueError("Date of birth cannot be in the future.")

    return value


def normalize_sex(value: Optional[str]) -> Optional[str]:
    cleaned_value = clean_optional_string(value)

    if cleaned_value is None:
        return None

    normalized_value = cleaned_value.lower()

    if normalized_value not in VALID_SEX_VALUES:
        raise InvalidPatientValueError(
            "Sex must be female, male, other, or unknown."
        )

    return normalized_value


def normalize_email(value) -> Optional[str]:
    cleaned_value = clean_optional_string(str(value) if value is not None else None)

    if cleaned_value is None:
        return None

    return cleaned_value.lower()


def clean_optional_string(value) -> Optional[str]:
    if value is None:
        return None

    cleaned_value = str(value).strip()

    return cleaned_value or None


def normalize_search(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None

    cleaned_value = value.strip()

    return cleaned_value or None
