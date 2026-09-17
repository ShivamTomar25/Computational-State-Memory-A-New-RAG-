from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.patient.model import Patient
from app.patient_information.models import ClinicalEncounter


def get_owned_patient(
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


def get_owned_encounter(
    db: Session,
    *,
    doctor_id: UUID,
    patient_id: UUID,
    encounter_id: UUID,
) -> Optional[ClinicalEncounter]:
    statement = (
        select(ClinicalEncounter)
        .join(Patient, ClinicalEncounter.patient_id == Patient.id)
        .where(
            ClinicalEncounter.id == encounter_id,
            ClinicalEncounter.patient_id == patient_id,
            Patient.doctor_id == doctor_id,
        )
    )

    return db.scalar(statement)


def get_owned_record(
    db: Session,
    *,
    model,
    doctor_id: UUID,
    patient_id: UUID,
    record_id: UUID,
):
    statement = (
        select(model)
        .join(Patient, model.patient_id == Patient.id)
        .where(
            model.id == record_id,
            model.patient_id == patient_id,
            Patient.doctor_id == doctor_id,
        )
    )

    return db.scalar(statement)


def list_owned_records(
    db: Session,
    *,
    model,
    doctor_id: UUID,
    patient_id: UUID,
    filters: list,
    order_by: list,
    offset: int,
    limit: int,
) -> list:
    statement = (
        select(model)
        .join(Patient, model.patient_id == Patient.id)
        .where(
            model.patient_id == patient_id,
            Patient.doctor_id == doctor_id,
            *filters,
        )
        .order_by(*order_by)
        .offset(offset)
        .limit(limit)
    )

    return list(db.scalars(statement).all())


def count_owned_records(
    db: Session,
    *,
    model,
    doctor_id: UUID,
    patient_id: UUID,
    filters: list,
) -> int:
    statement = (
        select(func.count())
        .select_from(model)
        .join(Patient, model.patient_id == Patient.id)
        .where(
            model.patient_id == patient_id,
            Patient.doctor_id == doctor_id,
            *filters,
        )
    )

    return int(db.scalar(statement) or 0)


def create_record(
    db: Session,
    *,
    model,
    data: dict,
):
    record = model(**data)
    db.add(record)
    db.flush()

    return record


def update_record(
    db: Session,
    *,
    record,
    data: dict,
):
    for field, value in data.items():
        setattr(record, field, value)

    db.flush()

    return record


def set_record_active(
    db: Session,
    *,
    record,
    is_active: bool,
):
    record.is_active = is_active
    db.flush()

    return record
