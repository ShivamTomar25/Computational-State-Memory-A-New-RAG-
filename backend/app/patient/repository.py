from typing import Optional
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.patient.model import Patient


def create_patient(
    db: Session,
    *,
    doctor_id: UUID,
    patient_code: str,
    full_name: str,
    date_of_birth,
    sex: Optional[str],
    phone: Optional[str],
    email: Optional[str],
    address: Optional[str],
    emergency_contact_name: Optional[str],
    emergency_contact_phone: Optional[str],
) -> Patient:
    patient = Patient(
        doctor_id=doctor_id,
        patient_code=patient_code,
        full_name=full_name,
        date_of_birth=date_of_birth,
        sex=sex,
        phone=phone,
        email=email,
        address=address,
        emergency_contact_name=emergency_contact_name,
        emergency_contact_phone=emergency_contact_phone,
    )

    db.add(patient)
    db.flush()

    return patient


def get_patient_by_id(
    db: Session,
    *,
    doctor_id: UUID,
    patient_id: UUID,
) -> Optional[Patient]:
    statement = select(Patient).where(
        Patient.id == patient_id,
        Patient.doctor_id == doctor_id,
    )

    return db.scalar(statement)


def get_patient_by_code(
    db: Session,
    *,
    doctor_id: UUID,
    patient_code: str,
) -> Optional[Patient]:
    statement = select(Patient).where(
        Patient.doctor_id == doctor_id,
        Patient.patient_code == patient_code,
    )

    return db.scalar(statement)


def list_patients(
    db: Session,
    *,
    doctor_id: UUID,
    offset: int,
    limit: int,
    search: Optional[str],
    include_archived: bool,
) -> list[Patient]:
    filters = build_patient_filters(
        doctor_id=doctor_id,
        search=search,
        include_archived=include_archived,
    )

    statement = (
        select(Patient)
        .where(*filters)
        .order_by(Patient.created_at.desc(), Patient.id.desc())
        .offset(offset)
        .limit(limit)
    )

    return list(db.scalars(statement).all())


def count_patients(
    db: Session,
    *,
    doctor_id: UUID,
    search: Optional[str],
    include_archived: bool,
) -> int:
    filters = build_patient_filters(
        doctor_id=doctor_id,
        search=search,
        include_archived=include_archived,
    )

    statement = select(func.count()).select_from(Patient).where(*filters)

    return int(db.scalar(statement) or 0)


def update_patient(
    db: Session,
    patient: Patient,
    update_data: dict,
) -> Patient:
    for field, value in update_data.items():
        setattr(patient, field, value)

    db.flush()

    return patient


def set_patient_active(
    db: Session,
    patient: Patient,
    is_active: bool,
) -> Patient:
    patient.is_active = is_active
    db.flush()

    return patient


def build_patient_filters(
    *,
    doctor_id: UUID,
    search: Optional[str],
    include_archived: bool,
) -> list:
    filters = [Patient.doctor_id == doctor_id]

    if not include_archived:
        filters.append(Patient.is_active.is_(True))

    if search:
        pattern = f"%{search}%"
        filters.append(
            or_(
                Patient.patient_code.ilike(pattern),
                Patient.full_name.ilike(pattern),
                Patient.phone.ilike(pattern),
                Patient.email.ilike(pattern),
            )
        )

    return filters
