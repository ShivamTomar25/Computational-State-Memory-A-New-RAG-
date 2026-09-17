from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.doctor.model import Doctor
from app.patient_information import repository
from app.patient_information.exceptions import (
    ClinicalRecordConflictError,
    EncounterPatientMismatchError,
    FinalClinicalNoteImmutableError,
    InvalidClinicalDateRangeError,
    InvalidClinicalValueError,
    InvalidObservationValueError,
    PatientInformationNotFoundError,
)
from app.patient_information.models import (
    Allergy,
    ClinicalEncounter,
    ClinicalNote,
    Measurement,
    MedicalCondition,
    Medication,
)
from app.patient_information.schemas import (
    AllergyCreate,
    AllergyListResponse,
    AllergyResponse,
    AllergyUpdate,
    ClinicalNoteCreate,
    ClinicalNoteListResponse,
    ClinicalNoteResponse,
    ClinicalNoteUpdate,
    ConditionCreate,
    ConditionListResponse,
    ConditionResponse,
    ConditionUpdate,
    EncounterCreate,
    EncounterListResponse,
    EncounterResponse,
    EncounterUpdate,
    MeasurementCreate,
    MeasurementListResponse,
    MeasurementResponse,
    MeasurementUpdate,
    MedicationCreate,
    MedicationListResponse,
    MedicationResponse,
    MedicationUpdate,
)


ENCOUNTER_TYPES = {
    "outpatient",
    "inpatient",
    "emergency",
    "telemedicine",
    "follow_up",
    "diagnostic",
    "other",
}
ENCOUNTER_STATUSES = {"planned", "in_progress", "completed", "cancelled"}
CONDITION_CATEGORIES = {"diagnosis", "symptom", "problem", "history", "risk"}
CONDITION_CLINICAL_STATUSES = {
    "active",
    "inactive",
    "resolved",
    "remission",
    "recurrent",
    "unknown",
}
CONDITION_VERIFICATION_STATUSES = {
    "suspected",
    "provisional",
    "confirmed",
    "refuted",
    "entered_in_error",
}
MEDICATION_STATUSES = {
    "planned",
    "active",
    "on_hold",
    "completed",
    "stopped",
    "cancelled",
    "entered_in_error",
    "unknown",
}
ALLERGY_TYPES = {"allergy", "intolerance"}
ALLERGY_CATEGORIES = {"medication", "food", "environment", "biologic", "other"}
ALLERGY_CLINICAL_STATUSES = {"active", "inactive", "resolved"}
ALLERGY_VERIFICATION_STATUSES = {
    "unconfirmed",
    "presumed",
    "confirmed",
    "refuted",
    "entered_in_error",
}
ALLERGY_CRITICALITIES = {"low", "high", "unable_to_assess"}
ALLERGY_SEVERITIES = {"mild", "moderate", "severe", "unknown"}
MEASUREMENT_STATUSES = {
    "preliminary",
    "final",
    "amended",
    "corrected",
    "cancelled",
    "entered_in_error",
}
MEASUREMENT_INTERPRETATIONS = {
    "low",
    "normal",
    "high",
    "critical",
    "abnormal",
    "unknown",
}
NOTE_TYPES = {
    "progress",
    "consultation",
    "discharge",
    "procedure",
    "assessment",
    "plan",
    "nursing",
    "administrative",
    "other",
}
NOTE_STATUSES = {"draft", "final", "amended", "entered_in_error"}
IMMUTABLE_NOTE_STATUSES = {"final", "amended"}
SOURCE_TYPES = {"manual_entry", "document_extraction", "external_import"}


def create_encounter(
    db: Session,
    *,
    doctor: Doctor,
    patient_id: UUID,
    data: EncounterCreate,
) -> ClinicalEncounter:
    ensure_patient_owned(db, doctor=doctor, patient_id=patient_id)
    payload = normalize_encounter(data.model_dump())
    payload.update(
        patient_id=patient_id,
        created_by_doctor_id=doctor.id,
    )

    return create_record(db, model=ClinicalEncounter, payload=payload)


def list_encounters(
    db: Session,
    *,
    doctor: Doctor,
    patient_id: UUID,
    page: int,
    page_size: int,
    include_archived: bool,
    status: Optional[str],
    encounter_type: Optional[str],
    search: Optional[str],
) -> EncounterListResponse:
    ensure_patient_owned(db, doctor=doctor, patient_id=patient_id)
    filters = active_filter(ClinicalEncounter, include_archived)

    if status:
        filters.append(ClinicalEncounter.status == normalize_choice(status, ENCOUNTER_STATUSES, "status"))

    if encounter_type:
        filters.append(ClinicalEncounter.encounter_type == normalize_choice(encounter_type, ENCOUNTER_TYPES, "encounter type"))

    normalized_search = clean_optional_string(search)

    if normalized_search:
        pattern = f"%{normalized_search}%"
        filters.append(
            or_(
                ClinicalEncounter.chief_complaint.ilike(pattern),
                ClinicalEncounter.summary.ilike(pattern),
            )
        )

    return list_records(
        db,
        model=ClinicalEncounter,
        response_model=EncounterResponse,
        list_model=EncounterListResponse,
        doctor=doctor,
        patient_id=patient_id,
        page=page,
        page_size=page_size,
        filters=filters,
        order_by=[ClinicalEncounter.started_at.desc(), ClinicalEncounter.id.desc()],
    )


def get_encounter(db: Session, *, doctor: Doctor, patient_id: UUID, record_id: UUID) -> ClinicalEncounter:
    return get_record(db, model=ClinicalEncounter, doctor=doctor, patient_id=patient_id, record_id=record_id)


def update_encounter(
    db: Session,
    *,
    doctor: Doctor,
    patient_id: UUID,
    record_id: UUID,
    data: EncounterUpdate,
) -> ClinicalEncounter:
    record = get_encounter(db, doctor=doctor, patient_id=patient_id, record_id=record_id)
    payload = normalize_encounter(data.model_dump(exclude_unset=True), partial=True)
    started_at = payload.get("started_at", record.started_at)
    ended_at = payload.get("ended_at", record.ended_at)
    validate_datetime_range(started_at, ended_at, "Encounter end time cannot be before start time.")

    return update_record(db, record=record, payload=payload)


def archive_encounter(db: Session, *, doctor: Doctor, patient_id: UUID, record_id: UUID) -> ClinicalEncounter:
    return set_active(db, record=get_encounter(db, doctor=doctor, patient_id=patient_id, record_id=record_id), is_active=False)


def restore_encounter(db: Session, *, doctor: Doctor, patient_id: UUID, record_id: UUID) -> ClinicalEncounter:
    return set_active(db, record=get_encounter(db, doctor=doctor, patient_id=patient_id, record_id=record_id), is_active=True)


def create_condition(db: Session, *, doctor: Doctor, patient_id: UUID, data: ConditionCreate) -> MedicalCondition:
    ensure_patient_owned(db, doctor=doctor, patient_id=patient_id)
    payload = normalize_condition(data.model_dump())
    ensure_encounter_matches_patient(db, doctor=doctor, patient_id=patient_id, encounter_id=payload.get("encounter_id"))
    payload.update(patient_id=patient_id, created_by_doctor_id=doctor.id)

    return create_record(db, model=MedicalCondition, payload=payload)


def list_conditions(
    db: Session,
    *,
    doctor: Doctor,
    patient_id: UUID,
    page: int,
    page_size: int,
    include_archived: bool,
    clinical_status: Optional[str],
    verification_status: Optional[str],
    category: Optional[str],
    search: Optional[str],
) -> ConditionListResponse:
    ensure_patient_owned(db, doctor=doctor, patient_id=patient_id)
    filters = active_filter(MedicalCondition, include_archived)

    if clinical_status:
        filters.append(MedicalCondition.clinical_status == normalize_choice(clinical_status, CONDITION_CLINICAL_STATUSES, "clinical status"))
    if verification_status:
        filters.append(MedicalCondition.verification_status == normalize_choice(verification_status, CONDITION_VERIFICATION_STATUSES, "verification status"))
    if category:
        filters.append(MedicalCondition.category == normalize_choice(category, CONDITION_CATEGORIES, "category"))

    normalized_search = clean_optional_string(search)

    if normalized_search:
        pattern = f"%{normalized_search}%"
        filters.append(or_(MedicalCondition.name.ilike(pattern), MedicalCondition.code.ilike(pattern)))

    return list_records(
        db,
        model=MedicalCondition,
        response_model=ConditionResponse,
        list_model=ConditionListResponse,
        doctor=doctor,
        patient_id=patient_id,
        page=page,
        page_size=page_size,
        filters=filters,
        order_by=[MedicalCondition.recorded_at.desc(), MedicalCondition.id.desc()],
    )


def get_condition(db: Session, *, doctor: Doctor, patient_id: UUID, record_id: UUID) -> MedicalCondition:
    return get_record(db, model=MedicalCondition, doctor=doctor, patient_id=patient_id, record_id=record_id)


def update_condition(db: Session, *, doctor: Doctor, patient_id: UUID, record_id: UUID, data: ConditionUpdate) -> MedicalCondition:
    record = get_condition(db, doctor=doctor, patient_id=patient_id, record_id=record_id)
    payload = normalize_condition(data.model_dump(exclude_unset=True), partial=True)
    ensure_encounter_matches_patient(db, doctor=doctor, patient_id=patient_id, encounter_id=payload.get("encounter_id"))
    onset_date = payload.get("onset_date", record.onset_date)
    resolved_date = payload.get("resolved_date", record.resolved_date)
    validate_date_range(onset_date, resolved_date, "Resolved date cannot be before onset date.")

    return update_record(db, record=record, payload=payload)


def archive_condition(db: Session, *, doctor: Doctor, patient_id: UUID, record_id: UUID) -> MedicalCondition:
    return set_active(db, record=get_condition(db, doctor=doctor, patient_id=patient_id, record_id=record_id), is_active=False)


def restore_condition(db: Session, *, doctor: Doctor, patient_id: UUID, record_id: UUID) -> MedicalCondition:
    return set_active(db, record=get_condition(db, doctor=doctor, patient_id=patient_id, record_id=record_id), is_active=True)


def create_medication(db: Session, *, doctor: Doctor, patient_id: UUID, data: MedicationCreate) -> Medication:
    ensure_patient_owned(db, doctor=doctor, patient_id=patient_id)
    payload = normalize_medication(data.model_dump())
    ensure_encounter_matches_patient(db, doctor=doctor, patient_id=patient_id, encounter_id=payload.get("encounter_id"))
    payload.update(patient_id=patient_id, created_by_doctor_id=doctor.id)

    return create_record(db, model=Medication, payload=payload)


def list_medications(
    db: Session,
    *,
    doctor: Doctor,
    patient_id: UUID,
    page: int,
    page_size: int,
    include_archived: bool,
    medication_status: Optional[str],
    encounter_id: Optional[UUID],
    search: Optional[str],
) -> MedicationListResponse:
    ensure_patient_owned(db, doctor=doctor, patient_id=patient_id)
    filters = active_filter(Medication, include_archived)

    if medication_status:
        filters.append(Medication.medication_status == normalize_choice(medication_status, MEDICATION_STATUSES, "medication status"))
    if encounter_id:
        filters.append(Medication.encounter_id == encounter_id)

    normalized_search = clean_optional_string(search)

    if normalized_search:
        pattern = f"%{normalized_search}%"
        filters.append(
            or_(
                Medication.medication_name.ilike(pattern),
                Medication.generic_name.ilike(pattern),
                Medication.medication_code.ilike(pattern),
            )
        )

    return list_records(
        db,
        model=Medication,
        response_model=MedicationResponse,
        list_model=MedicationListResponse,
        doctor=doctor,
        patient_id=patient_id,
        page=page,
        page_size=page_size,
        filters=filters,
        order_by=[Medication.recorded_at.desc(), Medication.id.desc()],
    )


def get_medication(db: Session, *, doctor: Doctor, patient_id: UUID, record_id: UUID) -> Medication:
    return get_record(db, model=Medication, doctor=doctor, patient_id=patient_id, record_id=record_id)


def update_medication(db: Session, *, doctor: Doctor, patient_id: UUID, record_id: UUID, data: MedicationUpdate) -> Medication:
    record = get_medication(db, doctor=doctor, patient_id=patient_id, record_id=record_id)
    payload = normalize_medication(data.model_dump(exclude_unset=True), partial=True)
    ensure_encounter_matches_patient(db, doctor=doctor, patient_id=patient_id, encounter_id=payload.get("encounter_id"))
    start_date = payload.get("start_date", record.start_date)
    end_date = payload.get("end_date", record.end_date)
    validate_date_range(start_date, end_date, "Medication end date cannot be before start date.")

    return update_record(db, record=record, payload=payload)


def archive_medication(db: Session, *, doctor: Doctor, patient_id: UUID, record_id: UUID) -> Medication:
    return set_active(db, record=get_medication(db, doctor=doctor, patient_id=patient_id, record_id=record_id), is_active=False)


def restore_medication(db: Session, *, doctor: Doctor, patient_id: UUID, record_id: UUID) -> Medication:
    return set_active(db, record=get_medication(db, doctor=doctor, patient_id=patient_id, record_id=record_id), is_active=True)


def create_allergy(db: Session, *, doctor: Doctor, patient_id: UUID, data: AllergyCreate) -> Allergy:
    ensure_patient_owned(db, doctor=doctor, patient_id=patient_id)
    payload = normalize_allergy(data.model_dump())
    ensure_encounter_matches_patient(db, doctor=doctor, patient_id=patient_id, encounter_id=payload.get("encounter_id"))
    payload.update(patient_id=patient_id, created_by_doctor_id=doctor.id)

    return create_record(db, model=Allergy, payload=payload)


def list_allergies(
    db: Session,
    *,
    doctor: Doctor,
    patient_id: UUID,
    page: int,
    page_size: int,
    include_archived: bool,
    clinical_status: Optional[str],
    verification_status: Optional[str],
    category: Optional[str],
    search: Optional[str],
) -> AllergyListResponse:
    ensure_patient_owned(db, doctor=doctor, patient_id=patient_id)
    filters = active_filter(Allergy, include_archived)

    if clinical_status:
        filters.append(Allergy.clinical_status == normalize_choice(clinical_status, ALLERGY_CLINICAL_STATUSES, "clinical status"))
    if verification_status:
        filters.append(Allergy.verification_status == normalize_choice(verification_status, ALLERGY_VERIFICATION_STATUSES, "verification status"))
    if category:
        filters.append(Allergy.category == normalize_choice(category, ALLERGY_CATEGORIES, "category"))

    normalized_search = clean_optional_string(search)

    if normalized_search:
        pattern = f"%{normalized_search}%"
        filters.append(or_(Allergy.substance.ilike(pattern), Allergy.reaction.ilike(pattern)))

    return list_records(
        db,
        model=Allergy,
        response_model=AllergyResponse,
        list_model=AllergyListResponse,
        doctor=doctor,
        patient_id=patient_id,
        page=page,
        page_size=page_size,
        filters=filters,
        order_by=[Allergy.recorded_at.desc(), Allergy.id.desc()],
    )


def get_allergy(db: Session, *, doctor: Doctor, patient_id: UUID, record_id: UUID) -> Allergy:
    return get_record(db, model=Allergy, doctor=doctor, patient_id=patient_id, record_id=record_id)


def update_allergy(db: Session, *, doctor: Doctor, patient_id: UUID, record_id: UUID, data: AllergyUpdate) -> Allergy:
    record = get_allergy(db, doctor=doctor, patient_id=patient_id, record_id=record_id)
    payload = normalize_allergy(data.model_dump(exclude_unset=True), partial=True)
    ensure_encounter_matches_patient(db, doctor=doctor, patient_id=patient_id, encounter_id=payload.get("encounter_id"))

    return update_record(db, record=record, payload=payload)


def archive_allergy(db: Session, *, doctor: Doctor, patient_id: UUID, record_id: UUID) -> Allergy:
    return set_active(db, record=get_allergy(db, doctor=doctor, patient_id=patient_id, record_id=record_id), is_active=False)


def restore_allergy(db: Session, *, doctor: Doctor, patient_id: UUID, record_id: UUID) -> Allergy:
    return set_active(db, record=get_allergy(db, doctor=doctor, patient_id=patient_id, record_id=record_id), is_active=True)


def create_measurement(db: Session, *, doctor: Doctor, patient_id: UUID, data: MeasurementCreate) -> Measurement:
    ensure_patient_owned(db, doctor=doctor, patient_id=patient_id)
    payload = normalize_measurement(data.model_dump())
    ensure_encounter_matches_patient(db, doctor=doctor, patient_id=patient_id, encounter_id=payload.get("encounter_id"))
    payload.update(patient_id=patient_id, created_by_doctor_id=doctor.id)

    return create_record(db, model=Measurement, payload=payload)


def list_measurements(
    db: Session,
    *,
    doctor: Doctor,
    patient_id: UUID,
    page: int,
    page_size: int,
    include_archived: bool,
    status: Optional[str],
    encounter_id: Optional[UUID],
    search: Optional[str],
) -> MeasurementListResponse:
    ensure_patient_owned(db, doctor=doctor, patient_id=patient_id)
    filters = active_filter(Measurement, include_archived)

    if status:
        filters.append(Measurement.status == normalize_choice(status, MEASUREMENT_STATUSES, "measurement status"))
    if encounter_id:
        filters.append(Measurement.encounter_id == encounter_id)

    normalized_search = clean_optional_string(search)

    if normalized_search:
        pattern = f"%{normalized_search}%"
        filters.append(or_(Measurement.observation_name.ilike(pattern), Measurement.observation_code.ilike(pattern)))

    return list_records(
        db,
        model=Measurement,
        response_model=MeasurementResponse,
        list_model=MeasurementListResponse,
        doctor=doctor,
        patient_id=patient_id,
        page=page,
        page_size=page_size,
        filters=filters,
        order_by=[Measurement.observed_at.desc(), Measurement.id.desc()],
    )


def get_measurement(db: Session, *, doctor: Doctor, patient_id: UUID, record_id: UUID) -> Measurement:
    return get_record(db, model=Measurement, doctor=doctor, patient_id=patient_id, record_id=record_id)


def update_measurement(db: Session, *, doctor: Doctor, patient_id: UUID, record_id: UUID, data: MeasurementUpdate) -> Measurement:
    record = get_measurement(db, doctor=doctor, patient_id=patient_id, record_id=record_id)
    payload = normalize_measurement(data.model_dump(exclude_unset=True), partial=True)
    ensure_encounter_matches_patient(db, doctor=doctor, patient_id=patient_id, encounter_id=payload.get("encounter_id"))
    value_numeric = payload.get("value_numeric", record.value_numeric)
    value_text = payload.get("value_text", record.value_text)
    validate_measurement_values(value_numeric, value_text)
    low = payload.get("reference_range_low", record.reference_range_low)
    high = payload.get("reference_range_high", record.reference_range_high)
    validate_reference_range(low, high)

    return update_record(db, record=record, payload=payload)


def archive_measurement(db: Session, *, doctor: Doctor, patient_id: UUID, record_id: UUID) -> Measurement:
    return set_active(db, record=get_measurement(db, doctor=doctor, patient_id=patient_id, record_id=record_id), is_active=False)


def restore_measurement(db: Session, *, doctor: Doctor, patient_id: UUID, record_id: UUID) -> Measurement:
    return set_active(db, record=get_measurement(db, doctor=doctor, patient_id=patient_id, record_id=record_id), is_active=True)


def create_note(db: Session, *, doctor: Doctor, patient_id: UUID, data: ClinicalNoteCreate) -> ClinicalNote:
    ensure_patient_owned(db, doctor=doctor, patient_id=patient_id)
    payload = normalize_note(data.model_dump())
    ensure_encounter_matches_patient(db, doctor=doctor, patient_id=patient_id, encounter_id=payload.get("encounter_id"))
    payload.update(patient_id=patient_id, created_by_doctor_id=doctor.id)

    return create_record(db, model=ClinicalNote, payload=payload)


def list_notes(
    db: Session,
    *,
    doctor: Doctor,
    patient_id: UUID,
    page: int,
    page_size: int,
    include_archived: bool,
    note_type: Optional[str],
    status: Optional[str],
    encounter_id: Optional[UUID],
    search: Optional[str],
) -> ClinicalNoteListResponse:
    ensure_patient_owned(db, doctor=doctor, patient_id=patient_id)
    filters = active_filter(ClinicalNote, include_archived)

    if note_type:
        filters.append(ClinicalNote.note_type == normalize_choice(note_type, NOTE_TYPES, "note type"))
    if status:
        filters.append(ClinicalNote.status == normalize_choice(status, NOTE_STATUSES, "note status"))
    if encounter_id:
        filters.append(ClinicalNote.encounter_id == encounter_id)

    normalized_search = clean_optional_string(search)

    if normalized_search:
        pattern = f"%{normalized_search}%"
        filters.append(or_(ClinicalNote.title.ilike(pattern), ClinicalNote.content.ilike(pattern)))

    return list_records(
        db,
        model=ClinicalNote,
        response_model=ClinicalNoteResponse,
        list_model=ClinicalNoteListResponse,
        doctor=doctor,
        patient_id=patient_id,
        page=page,
        page_size=page_size,
        filters=filters,
        order_by=[ClinicalNote.authored_at.desc(), ClinicalNote.id.desc()],
    )


def get_note(db: Session, *, doctor: Doctor, patient_id: UUID, record_id: UUID) -> ClinicalNote:
    return get_record(db, model=ClinicalNote, doctor=doctor, patient_id=patient_id, record_id=record_id)


def update_note(db: Session, *, doctor: Doctor, patient_id: UUID, record_id: UUID, data: ClinicalNoteUpdate) -> ClinicalNote:
    record = get_note(db, doctor=doctor, patient_id=patient_id, record_id=record_id)

    if record.status in IMMUTABLE_NOTE_STATUSES:
        raise FinalClinicalNoteImmutableError("Final or amended clinical notes cannot be edited.")

    payload = normalize_note(data.model_dump(exclude_unset=True), partial=True)
    ensure_encounter_matches_patient(db, doctor=doctor, patient_id=patient_id, encounter_id=payload.get("encounter_id"))

    return update_record(db, record=record, payload=payload)


def archive_note(db: Session, *, doctor: Doctor, patient_id: UUID, record_id: UUID) -> ClinicalNote:
    return set_active(db, record=get_note(db, doctor=doctor, patient_id=patient_id, record_id=record_id), is_active=False)


def restore_note(db: Session, *, doctor: Doctor, patient_id: UUID, record_id: UUID) -> ClinicalNote:
    return set_active(db, record=get_note(db, doctor=doctor, patient_id=patient_id, record_id=record_id), is_active=True)


def ensure_patient_owned(db: Session, *, doctor: Doctor, patient_id: UUID) -> None:
    patient = repository.get_owned_patient(db, doctor_id=doctor.id, patient_id=patient_id)

    if patient is None:
        raise PatientInformationNotFoundError("Patient not found.")


def ensure_encounter_matches_patient(
    db: Session,
    *,
    doctor: Doctor,
    patient_id: UUID,
    encounter_id: Optional[UUID],
) -> None:
    if encounter_id is None:
        return

    encounter = repository.get_owned_encounter(
        db,
        doctor_id=doctor.id,
        patient_id=patient_id,
        encounter_id=encounter_id,
    )

    if encounter is None:
        raise EncounterPatientMismatchError("Encounter not found for this patient.")


def create_record(db: Session, *, model, payload: dict):
    try:
        record = repository.create_record(db, model=model, data=payload)
        db.commit()
        db.refresh(record)

        return record
    except IntegrityError as error:
        db.rollback()
        raise ClinicalRecordConflictError("Clinical record could not be saved.") from error


def update_record(db: Session, *, record, payload: dict):
    if not payload:
        return record

    try:
        updated_record = repository.update_record(db, record=record, data=payload)
        db.commit()
        db.refresh(updated_record)

        return updated_record
    except IntegrityError as error:
        db.rollback()
        raise ClinicalRecordConflictError("Clinical record could not be updated.") from error


def set_active(db: Session, *, record, is_active: bool):
    if record.is_active == is_active:
        return record

    try:
        updated_record = repository.set_record_active(
            db,
            record=record,
            is_active=is_active,
        )
        db.commit()
        db.refresh(updated_record)

        return updated_record
    except IntegrityError as error:
        db.rollback()
        raise ClinicalRecordConflictError("Clinical record status could not be updated.") from error


def get_record(db: Session, *, model, doctor: Doctor, patient_id: UUID, record_id: UUID):
    record = repository.get_owned_record(
        db,
        model=model,
        doctor_id=doctor.id,
        patient_id=patient_id,
        record_id=record_id,
    )

    if record is None:
        raise PatientInformationNotFoundError("Clinical record not found.")

    return record


def list_records(
    db: Session,
    *,
    model,
    response_model,
    list_model,
    doctor: Doctor,
    patient_id: UUID,
    page: int,
    page_size: int,
    filters: list,
    order_by: list,
):
    offset = (page - 1) * page_size
    total = repository.count_owned_records(
        db,
        model=model,
        doctor_id=doctor.id,
        patient_id=patient_id,
        filters=filters,
    )
    records = repository.list_owned_records(
        db,
        model=model,
        doctor_id=doctor.id,
        patient_id=patient_id,
        filters=filters,
        order_by=order_by,
        offset=offset,
        limit=page_size,
    )
    total_pages = (total + page_size - 1) // page_size if total else 0

    return list_model(
        items=[response_model.model_validate(record) for record in records],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


def active_filter(model, include_archived: bool) -> list:
    return [] if include_archived else [model.is_active.is_(True)]


def normalize_encounter(values: dict[str, Any], *, partial: bool = False) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    copy_required_choice(values, normalized, "encounter_type", ENCOUNTER_TYPES, "encounter type", partial)
    copy_required_choice(values, normalized, "status", ENCOUNTER_STATUSES, "status", partial)
    copy_value(values, normalized, "started_at")
    copy_value(values, normalized, "ended_at")
    copy_clean_optional(values, normalized, "chief_complaint")
    copy_clean_optional(values, normalized, "summary")
    copy_clean_optional(values, normalized, "location")

    if "started_at" in normalized and "ended_at" in normalized:
        validate_datetime_range(normalized["started_at"], normalized["ended_at"], "Encounter end time cannot be before start time.")

    return normalized


def normalize_condition(values: dict[str, Any], *, partial: bool = False) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    copy_value(values, normalized, "encounter_id")
    copy_required_string(values, normalized, "name", "Condition name", partial)
    copy_clean_optional(values, normalized, "code")
    copy_clean_optional(values, normalized, "code_system")
    copy_required_choice(values, normalized, "category", CONDITION_CATEGORIES, "category", partial)
    copy_required_choice(values, normalized, "clinical_status", CONDITION_CLINICAL_STATUSES, "clinical status", partial)
    copy_required_choice(values, normalized, "verification_status", CONDITION_VERIFICATION_STATUSES, "verification status", partial)
    copy_clean_optional(values, normalized, "severity")
    copy_value(values, normalized, "onset_date")
    copy_value(values, normalized, "resolved_date")
    copy_clean_optional(values, normalized, "notes")
    copy_source(values, normalized, partial=partial)
    validate_date_range(normalized.get("onset_date"), normalized.get("resolved_date"), "Resolved date cannot be before onset date.")

    return normalized


def normalize_medication(values: dict[str, Any], *, partial: bool = False) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    copy_value(values, normalized, "encounter_id")
    copy_required_string(values, normalized, "medication_name", "Medication name", partial)
    for field in ("generic_name", "medication_code", "code_system", "dosage_unit", "route", "frequency", "instructions", "reason", "prescribed_by"):
        copy_clean_optional(values, normalized, field)
    copy_decimal(values, normalized, "dosage_value")
    copy_required_choice(values, normalized, "medication_status", MEDICATION_STATUSES, "medication status", partial)
    copy_value(values, normalized, "start_date")
    copy_value(values, normalized, "end_date")
    copy_source(values, normalized, partial=partial)

    if normalized.get("dosage_value") is not None and normalized["dosage_value"] < 0:
        raise InvalidClinicalValueError("Dosage value cannot be negative.")

    validate_date_range(normalized.get("start_date"), normalized.get("end_date"), "Medication end date cannot be before start date.")

    return normalized


def normalize_allergy(values: dict[str, Any], *, partial: bool = False) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    copy_value(values, normalized, "encounter_id")
    copy_required_string(values, normalized, "substance", "Substance", partial)
    copy_clean_optional(values, normalized, "substance_code")
    copy_clean_optional(values, normalized, "code_system")
    copy_required_choice(values, normalized, "allergy_type", ALLERGY_TYPES, "allergy type", partial)
    copy_optional_choice(values, normalized, "category", ALLERGY_CATEGORIES, "category")
    copy_required_choice(values, normalized, "clinical_status", ALLERGY_CLINICAL_STATUSES, "clinical status", partial)
    copy_required_choice(values, normalized, "verification_status", ALLERGY_VERIFICATION_STATUSES, "verification status", partial)
    copy_optional_choice(values, normalized, "criticality", ALLERGY_CRITICALITIES, "criticality")
    copy_clean_optional(values, normalized, "reaction")
    copy_optional_choice(values, normalized, "severity", ALLERGY_SEVERITIES, "severity")
    copy_value(values, normalized, "onset_date")
    copy_clean_optional(values, normalized, "notes")
    copy_source(values, normalized, partial=partial)

    return normalized


def normalize_measurement(values: dict[str, Any], *, partial: bool = False) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    copy_value(values, normalized, "encounter_id")
    copy_required_string(values, normalized, "observation_name", "Observation name", partial)
    copy_clean_optional(values, normalized, "observation_code")
    copy_clean_optional(values, normalized, "code_system")
    copy_decimal(values, normalized, "value_numeric")
    copy_clean_optional(values, normalized, "value_text")
    copy_clean_optional(values, normalized, "unit")
    copy_decimal(values, normalized, "reference_range_low")
    copy_decimal(values, normalized, "reference_range_high")
    copy_optional_choice(values, normalized, "interpretation", MEASUREMENT_INTERPRETATIONS, "interpretation")
    copy_required_choice(values, normalized, "status", MEASUREMENT_STATUSES, "measurement status", partial)
    copy_value(values, normalized, "observed_at")
    copy_source(values, normalized, partial=partial)
    copy_clean_optional(values, normalized, "notes")

    if not partial:
        validate_measurement_values(normalized.get("value_numeric"), normalized.get("value_text"))

    validate_reference_range(normalized.get("reference_range_low"), normalized.get("reference_range_high"))

    return normalized


def normalize_note(values: dict[str, Any], *, partial: bool = False) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    copy_value(values, normalized, "encounter_id")
    copy_required_choice(values, normalized, "note_type", NOTE_TYPES, "note type", partial)
    copy_clean_optional(values, normalized, "title")
    copy_required_string(values, normalized, "content", "Note content", partial)
    copy_required_choice(values, normalized, "status", NOTE_STATUSES, "note status", partial)
    copy_value(values, normalized, "authored_at")
    copy_source(values, normalized, partial=partial)

    return normalized


def copy_value(source: dict[str, Any], target: dict[str, Any], field: str) -> None:
    if field in source:
        target[field] = source[field]


def copy_decimal(source: dict[str, Any], target: dict[str, Any], field: str) -> None:
    if field in source:
        target[field] = source[field]


def copy_required_string(
    source: dict[str, Any],
    target: dict[str, Any],
    field: str,
    label: str,
    partial: bool,
) -> None:
    if field not in source:
        if partial:
            return
        raise InvalidClinicalValueError(f"{label} is required.")

    value = clean_required_string(source[field], label)
    target[field] = value


def copy_clean_optional(source: dict[str, Any], target: dict[str, Any], field: str) -> None:
    if field in source:
        target[field] = clean_optional_string(source[field])


def copy_required_choice(
    source: dict[str, Any],
    target: dict[str, Any],
    field: str,
    choices: set[str],
    label: str,
    partial: bool,
) -> None:
    if field not in source:
        if partial:
            return
        raise InvalidClinicalValueError(f"{label.title()} is required.")

    target[field] = normalize_choice(source[field], choices, label)


def copy_optional_choice(
    source: dict[str, Any],
    target: dict[str, Any],
    field: str,
    choices: set[str],
    label: str,
) -> None:
    if field not in source:
        return

    value = clean_optional_string(source[field])

    if value is None:
        target[field] = None
        return

    target[field] = normalize_choice(value, choices, label)


def copy_source(source: dict[str, Any], target: dict[str, Any], *, partial: bool) -> None:
    if "source_type" in source:
        value = clean_optional_string(source["source_type"])
        target["source_type"] = normalize_source_type(value)
    elif not partial and "source_type" not in target:
        target["source_type"] = "manual_entry"

    copy_clean_optional(source, target, "source_reference")


def normalize_source_type(value: Optional[str]) -> str:
    if value is None:
        return "manual_entry"

    normalized = value.strip().lower()

    if normalized == "system_generated":
        raise InvalidClinicalValueError("System-generated source type is not allowed for manual API entry.")

    if normalized not in SOURCE_TYPES:
        raise InvalidClinicalValueError("Source type is invalid.")

    return normalized


def normalize_choice(value: str, choices: set[str], label: str) -> str:
    normalized = clean_required_string(value, label).lower()

    if normalized not in choices:
        raise InvalidClinicalValueError(f"{label.title()} is invalid.")

    return normalized


def clean_required_string(value, label: str) -> str:
    cleaned = str(value).strip()

    if not cleaned:
        raise InvalidClinicalValueError(f"{label} cannot be blank.")

    return cleaned


def clean_optional_string(value) -> Optional[str]:
    if value is None:
        return None

    cleaned = str(value).strip()

    return cleaned or None


def validate_datetime_range(started_at: Optional[datetime], ended_at: Optional[datetime], message: str) -> None:
    if started_at is not None and ended_at is not None and ended_at < started_at:
        raise InvalidClinicalDateRangeError(message)


def validate_date_range(start_date: Optional[date], end_date: Optional[date], message: str) -> None:
    if start_date is not None and end_date is not None and end_date < start_date:
        raise InvalidClinicalDateRangeError(message)


def validate_measurement_values(value_numeric: Optional[Decimal], value_text: Optional[str]) -> None:
    if value_numeric is None and clean_optional_string(value_text) is None:
        raise InvalidObservationValueError("A measurement requires a numeric or text value.")


def validate_reference_range(low: Optional[Decimal], high: Optional[Decimal]) -> None:
    if low is not None and high is not None and low > high:
        raise InvalidObservationValueError("Reference range low cannot exceed high.")
