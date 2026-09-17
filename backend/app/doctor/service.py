from typing import Any, Optional
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.doctor import repository
from app.doctor.exceptions import (
    DoctorEmailAlreadyExistsError,
    DoctorLicenseAlreadyExistsError,
    DoctorNotFoundError,
    InactiveDoctorError,
    InvalidDoctorCredentialsError,
)
from app.doctor.model import Doctor
from app.doctor.schemas import DoctorCreate, DoctorLogin, DoctorUpdate
from app.security.password import hash_password, verify_password


def register_doctor(
    db: Session,
    doctor_data: DoctorCreate,
) -> Doctor:
    normalized_email = str(doctor_data.email).strip().lower()

    existing_doctor = repository.get_doctor_by_email(
        db=db,
        email=normalized_email,
    )

    if existing_doctor is not None:
        raise DoctorEmailAlreadyExistsError(
            "A doctor with this email already exists."
        )

    normalized_license: Optional[str] = None

    if doctor_data.medical_license_number:
        normalized_license = doctor_data.medical_license_number.strip().upper()

        existing_license = repository.get_doctor_by_license_number(
            db=db,
            medical_license_number=normalized_license,
        )

        if existing_license is not None:
            raise DoctorLicenseAlreadyExistsError(
                "A doctor with this medical license already exists."
            )
    password_hash = hash_password(doctor_data.password)

    try:
        doctor = repository.create_doctor(
            db=db,
            full_name=doctor_data.full_name,
            email=normalized_email,
            password_hash=password_hash,
            specialization=doctor_data.specialization,
            medical_license_number=normalized_license,
            organization_name=doctor_data.organization_name,
        )

        db.commit()
        db.refresh(doctor)

        return doctor

    except IntegrityError as error:
        db.rollback()

        raise DoctorEmailAlreadyExistsError(
            "Doctor registration conflicts with an existing record."
        ) from error


def authenticate_doctor(
    db: Session,
    login_data: DoctorLogin,
) -> Doctor:
    normalized_email = str(login_data.email).strip().lower()

    doctor = repository.get_doctor_by_email(
        db=db,
        email=normalized_email,
    )

    if doctor is None:
        raise InvalidDoctorCredentialsError("Invalid email or password.")

    password_is_valid = verify_password(
        plain_password=login_data.password,
        hashed_password=doctor.password_hash,
    )

    if not password_is_valid:
        raise InvalidDoctorCredentialsError("Invalid email or password.")

    if not doctor.is_active:
        raise InactiveDoctorError("This doctor account is inactive.")

    return doctor


def get_doctor(
    db: Session,
    doctor_id: UUID,
) -> Doctor:
    doctor = repository.get_doctor_by_id(
        db=db,
        doctor_id=doctor_id,
    )

    if doctor is None:
        raise DoctorNotFoundError(
            "Doctor not found."
        )

    return doctor


def update_doctor_profile(
    db: Session,
    doctor: Doctor,
    doctor_data: DoctorUpdate,
) -> Doctor:
    update_data: dict[str, Any] = doctor_data.model_dump(exclude_unset=True)

    if not update_data:
        return doctor

    if "full_name" in update_data:
        full_name = update_data["full_name"]

        if full_name is not None:
            update_data["full_name"] = full_name.strip()

    for optional_field in ("specialization", "organization_name"):
        if optional_field in update_data:
            value = update_data[optional_field]

            update_data[optional_field] = value.strip() if value else None

    if "medical_license_number" in update_data:
        license_number = update_data["medical_license_number"]

        if license_number:
            normalized_license = license_number.strip().upper()

            existing_doctor = repository.get_doctor_by_license_number(
                db=db,
                medical_license_number=normalized_license,
            )

            if existing_doctor is not None and existing_doctor.id != doctor.id:
                raise DoctorLicenseAlreadyExistsError(
                    "This medical license belongs to another doctor."
                )

            update_data["medical_license_number"] = normalized_license
        else:
            update_data["medical_license_number"] = None

    try:
        updated_doctor = repository.update_doctor(
            db=db,
            doctor=doctor,
            update_data=update_data,
        )

        db.commit()
        db.refresh(updated_doctor)

        return updated_doctor

    except IntegrityError as error:
        db.rollback()

        raise DoctorLicenseAlreadyExistsError(
            "The updated profile conflicts with an existing doctor."
        ) from error
