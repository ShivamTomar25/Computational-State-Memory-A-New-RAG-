from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.doctor.model import Doctor


def get_doctor_by_id(
    db: Session,
    doctor_id: UUID,
) -> Optional[Doctor]:
    statement = select(Doctor).where(
        Doctor.id == doctor_id
    )

    return db.scalar(statement)


def get_doctor_by_email(
    db: Session,
    email: str,
) -> Optional[Doctor]:
    normalized_email = email.strip().lower()

    statement = select(Doctor).where(
        Doctor.email == normalized_email
    )

    return db.scalar(statement)


def get_doctor_by_license_number(
    db: Session,
    medical_license_number: str,
) -> Optional[Doctor]:
    normalized_license = medical_license_number.strip().upper()

    statement = select(Doctor).where(
        Doctor.medical_license_number == normalized_license
    )

    return db.scalar(statement)


def create_doctor(
    db: Session,
    *,
    full_name: str,
    email: str,
    password_hash: str,
    specialization: Optional[str] = None,
    medical_license_number: Optional[str] = None,
    organization_name: Optional[str] = None,
) -> Doctor:
    doctor = Doctor(
        full_name=full_name.strip(),
        email=email.strip().lower(),
        password_hash=password_hash,
        specialization=specialization.strip() if specialization else None,
        medical_license_number=(
            medical_license_number.strip().upper()
            if medical_license_number
            else None
        ),
        organization_name=organization_name.strip() if organization_name else None,
    )

    db.add(doctor)
    db.flush()

    return doctor


def update_doctor(
    db: Session,
    doctor: Doctor,
    update_data: dict[str, Any],
) -> Doctor:
    for field, value in update_data.items():
        setattr(doctor, field, value)

    db.flush()

    return doctor
