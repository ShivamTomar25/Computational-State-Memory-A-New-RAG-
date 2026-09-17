from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.doctor.dependencies import CurrentDoctor
from app.patient_information.exceptions import (
    ClinicalRecordConflictError,
    EncounterPatientMismatchError,
    FinalClinicalNoteImmutableError,
    InvalidClinicalDateRangeError,
    InvalidClinicalValueError,
    InvalidObservationValueError,
    PatientInformationError,
    PatientInformationNotFoundError,
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
from app.patient_information import service


router = APIRouter(
    prefix="/api/patients/{patient_id}",
)


DatabaseSession = Annotated[Session, Depends(get_db)]
Page = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]


@router.post("/encounters", response_model=EncounterResponse, status_code=status.HTTP_201_CREATED, tags=["Patient Encounters"])
def create_encounter(patient_id: UUID, data: EncounterCreate, current_doctor: CurrentDoctor, db: DatabaseSession) -> EncounterResponse:
    try:
        record = service.create_encounter(db, doctor=current_doctor, patient_id=patient_id, data=data)
        return EncounterResponse.model_validate(record)
    except PatientInformationError as error:
        raise to_http_exception(error) from error


@router.get("/encounters", response_model=EncounterListResponse, tags=["Patient Encounters"])
def list_encounters(
    patient_id: UUID,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
    page: Page = 1,
    page_size: PageSize = 20,
    include_archived: bool = False,
    status: Optional[str] = None,
    encounter_type: Optional[str] = None,
    search: Optional[str] = None,
) -> EncounterListResponse:
    try:
        return service.list_encounters(
            db,
            doctor=current_doctor,
            patient_id=patient_id,
            page=page,
            page_size=page_size,
            include_archived=include_archived,
            status=status,
            encounter_type=encounter_type,
            search=search,
        )
    except PatientInformationError as error:
        raise to_http_exception(error) from error


@router.get("/encounters/{record_id}", response_model=EncounterResponse, tags=["Patient Encounters"])
def get_encounter(patient_id: UUID, record_id: UUID, current_doctor: CurrentDoctor, db: DatabaseSession) -> EncounterResponse:
    try:
        return EncounterResponse.model_validate(service.get_encounter(db, doctor=current_doctor, patient_id=patient_id, record_id=record_id))
    except PatientInformationError as error:
        raise to_http_exception(error) from error


@router.patch("/encounters/{record_id}", response_model=EncounterResponse, tags=["Patient Encounters"])
def update_encounter(patient_id: UUID, record_id: UUID, data: EncounterUpdate, current_doctor: CurrentDoctor, db: DatabaseSession) -> EncounterResponse:
    try:
        return EncounterResponse.model_validate(service.update_encounter(db, doctor=current_doctor, patient_id=patient_id, record_id=record_id, data=data))
    except PatientInformationError as error:
        raise to_http_exception(error) from error


@router.post("/encounters/{record_id}/archive", response_model=EncounterResponse, tags=["Patient Encounters"])
def archive_encounter(patient_id: UUID, record_id: UUID, current_doctor: CurrentDoctor, db: DatabaseSession) -> EncounterResponse:
    try:
        return EncounterResponse.model_validate(service.archive_encounter(db, doctor=current_doctor, patient_id=patient_id, record_id=record_id))
    except PatientInformationError as error:
        raise to_http_exception(error) from error


@router.post("/encounters/{record_id}/restore", response_model=EncounterResponse, tags=["Patient Encounters"])
def restore_encounter(patient_id: UUID, record_id: UUID, current_doctor: CurrentDoctor, db: DatabaseSession) -> EncounterResponse:
    try:
        return EncounterResponse.model_validate(service.restore_encounter(db, doctor=current_doctor, patient_id=patient_id, record_id=record_id))
    except PatientInformationError as error:
        raise to_http_exception(error) from error


@router.post("/conditions", response_model=ConditionResponse, status_code=status.HTTP_201_CREATED, tags=["Patient Conditions"])
def create_condition(patient_id: UUID, data: ConditionCreate, current_doctor: CurrentDoctor, db: DatabaseSession) -> ConditionResponse:
    try:
        return ConditionResponse.model_validate(service.create_condition(db, doctor=current_doctor, patient_id=patient_id, data=data))
    except PatientInformationError as error:
        raise to_http_exception(error) from error


@router.get("/conditions", response_model=ConditionListResponse, tags=["Patient Conditions"])
def list_conditions(
    patient_id: UUID,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
    page: Page = 1,
    page_size: PageSize = 20,
    include_archived: bool = False,
    clinical_status: Optional[str] = None,
    verification_status: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
) -> ConditionListResponse:
    try:
        return service.list_conditions(
            db,
            doctor=current_doctor,
            patient_id=patient_id,
            page=page,
            page_size=page_size,
            include_archived=include_archived,
            clinical_status=clinical_status,
            verification_status=verification_status,
            category=category,
            search=search,
        )
    except PatientInformationError as error:
        raise to_http_exception(error) from error


@router.get("/conditions/{record_id}", response_model=ConditionResponse, tags=["Patient Conditions"])
def get_condition(patient_id: UUID, record_id: UUID, current_doctor: CurrentDoctor, db: DatabaseSession) -> ConditionResponse:
    try:
        return ConditionResponse.model_validate(service.get_condition(db, doctor=current_doctor, patient_id=patient_id, record_id=record_id))
    except PatientInformationError as error:
        raise to_http_exception(error) from error


@router.patch("/conditions/{record_id}", response_model=ConditionResponse, tags=["Patient Conditions"])
def update_condition(patient_id: UUID, record_id: UUID, data: ConditionUpdate, current_doctor: CurrentDoctor, db: DatabaseSession) -> ConditionResponse:
    try:
        return ConditionResponse.model_validate(service.update_condition(db, doctor=current_doctor, patient_id=patient_id, record_id=record_id, data=data))
    except PatientInformationError as error:
        raise to_http_exception(error) from error


@router.post("/conditions/{record_id}/archive", response_model=ConditionResponse, tags=["Patient Conditions"])
def archive_condition(patient_id: UUID, record_id: UUID, current_doctor: CurrentDoctor, db: DatabaseSession) -> ConditionResponse:
    try:
        return ConditionResponse.model_validate(service.archive_condition(db, doctor=current_doctor, patient_id=patient_id, record_id=record_id))
    except PatientInformationError as error:
        raise to_http_exception(error) from error


@router.post("/conditions/{record_id}/restore", response_model=ConditionResponse, tags=["Patient Conditions"])
def restore_condition(patient_id: UUID, record_id: UUID, current_doctor: CurrentDoctor, db: DatabaseSession) -> ConditionResponse:
    try:
        return ConditionResponse.model_validate(service.restore_condition(db, doctor=current_doctor, patient_id=patient_id, record_id=record_id))
    except PatientInformationError as error:
        raise to_http_exception(error) from error


@router.post("/medications", response_model=MedicationResponse, status_code=status.HTTP_201_CREATED, tags=["Patient Medications"])
def create_medication(patient_id: UUID, data: MedicationCreate, current_doctor: CurrentDoctor, db: DatabaseSession) -> MedicationResponse:
    try:
        return MedicationResponse.model_validate(service.create_medication(db, doctor=current_doctor, patient_id=patient_id, data=data))
    except PatientInformationError as error:
        raise to_http_exception(error) from error


@router.get("/medications", response_model=MedicationListResponse, tags=["Patient Medications"])
def list_medications(
    patient_id: UUID,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
    page: Page = 1,
    page_size: PageSize = 20,
    include_archived: bool = False,
    medication_status: Optional[str] = None,
    encounter_id: Optional[UUID] = None,
    search: Optional[str] = None,
) -> MedicationListResponse:
    try:
        return service.list_medications(
            db,
            doctor=current_doctor,
            patient_id=patient_id,
            page=page,
            page_size=page_size,
            include_archived=include_archived,
            medication_status=medication_status,
            encounter_id=encounter_id,
            search=search,
        )
    except PatientInformationError as error:
        raise to_http_exception(error) from error


@router.get("/medications/{record_id}", response_model=MedicationResponse, tags=["Patient Medications"])
def get_medication(patient_id: UUID, record_id: UUID, current_doctor: CurrentDoctor, db: DatabaseSession) -> MedicationResponse:
    try:
        return MedicationResponse.model_validate(service.get_medication(db, doctor=current_doctor, patient_id=patient_id, record_id=record_id))
    except PatientInformationError as error:
        raise to_http_exception(error) from error


@router.patch("/medications/{record_id}", response_model=MedicationResponse, tags=["Patient Medications"])
def update_medication(patient_id: UUID, record_id: UUID, data: MedicationUpdate, current_doctor: CurrentDoctor, db: DatabaseSession) -> MedicationResponse:
    try:
        return MedicationResponse.model_validate(service.update_medication(db, doctor=current_doctor, patient_id=patient_id, record_id=record_id, data=data))
    except PatientInformationError as error:
        raise to_http_exception(error) from error


@router.post("/medications/{record_id}/archive", response_model=MedicationResponse, tags=["Patient Medications"])
def archive_medication(patient_id: UUID, record_id: UUID, current_doctor: CurrentDoctor, db: DatabaseSession) -> MedicationResponse:
    try:
        return MedicationResponse.model_validate(service.archive_medication(db, doctor=current_doctor, patient_id=patient_id, record_id=record_id))
    except PatientInformationError as error:
        raise to_http_exception(error) from error


@router.post("/medications/{record_id}/restore", response_model=MedicationResponse, tags=["Patient Medications"])
def restore_medication(patient_id: UUID, record_id: UUID, current_doctor: CurrentDoctor, db: DatabaseSession) -> MedicationResponse:
    try:
        return MedicationResponse.model_validate(service.restore_medication(db, doctor=current_doctor, patient_id=patient_id, record_id=record_id))
    except PatientInformationError as error:
        raise to_http_exception(error) from error


@router.post("/allergies", response_model=AllergyResponse, status_code=status.HTTP_201_CREATED, tags=["Patient Allergies"])
def create_allergy(patient_id: UUID, data: AllergyCreate, current_doctor: CurrentDoctor, db: DatabaseSession) -> AllergyResponse:
    try:
        return AllergyResponse.model_validate(service.create_allergy(db, doctor=current_doctor, patient_id=patient_id, data=data))
    except PatientInformationError as error:
        raise to_http_exception(error) from error


@router.get("/allergies", response_model=AllergyListResponse, tags=["Patient Allergies"])
def list_allergies(
    patient_id: UUID,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
    page: Page = 1,
    page_size: PageSize = 20,
    include_archived: bool = False,
    clinical_status: Optional[str] = None,
    verification_status: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
) -> AllergyListResponse:
    try:
        return service.list_allergies(
            db,
            doctor=current_doctor,
            patient_id=patient_id,
            page=page,
            page_size=page_size,
            include_archived=include_archived,
            clinical_status=clinical_status,
            verification_status=verification_status,
            category=category,
            search=search,
        )
    except PatientInformationError as error:
        raise to_http_exception(error) from error


@router.get("/allergies/{record_id}", response_model=AllergyResponse, tags=["Patient Allergies"])
def get_allergy(patient_id: UUID, record_id: UUID, current_doctor: CurrentDoctor, db: DatabaseSession) -> AllergyResponse:
    try:
        return AllergyResponse.model_validate(service.get_allergy(db, doctor=current_doctor, patient_id=patient_id, record_id=record_id))
    except PatientInformationError as error:
        raise to_http_exception(error) from error


@router.patch("/allergies/{record_id}", response_model=AllergyResponse, tags=["Patient Allergies"])
def update_allergy(patient_id: UUID, record_id: UUID, data: AllergyUpdate, current_doctor: CurrentDoctor, db: DatabaseSession) -> AllergyResponse:
    try:
        return AllergyResponse.model_validate(service.update_allergy(db, doctor=current_doctor, patient_id=patient_id, record_id=record_id, data=data))
    except PatientInformationError as error:
        raise to_http_exception(error) from error


@router.post("/allergies/{record_id}/archive", response_model=AllergyResponse, tags=["Patient Allergies"])
def archive_allergy(patient_id: UUID, record_id: UUID, current_doctor: CurrentDoctor, db: DatabaseSession) -> AllergyResponse:
    try:
        return AllergyResponse.model_validate(service.archive_allergy(db, doctor=current_doctor, patient_id=patient_id, record_id=record_id))
    except PatientInformationError as error:
        raise to_http_exception(error) from error


@router.post("/allergies/{record_id}/restore", response_model=AllergyResponse, tags=["Patient Allergies"])
def restore_allergy(patient_id: UUID, record_id: UUID, current_doctor: CurrentDoctor, db: DatabaseSession) -> AllergyResponse:
    try:
        return AllergyResponse.model_validate(service.restore_allergy(db, doctor=current_doctor, patient_id=patient_id, record_id=record_id))
    except PatientInformationError as error:
        raise to_http_exception(error) from error


@router.post("/measurements", response_model=MeasurementResponse, status_code=status.HTTP_201_CREATED, tags=["Patient Measurements"])
def create_measurement(patient_id: UUID, data: MeasurementCreate, current_doctor: CurrentDoctor, db: DatabaseSession) -> MeasurementResponse:
    try:
        return MeasurementResponse.model_validate(service.create_measurement(db, doctor=current_doctor, patient_id=patient_id, data=data))
    except PatientInformationError as error:
        raise to_http_exception(error) from error


@router.get("/measurements", response_model=MeasurementListResponse, tags=["Patient Measurements"])
def list_measurements(
    patient_id: UUID,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
    page: Page = 1,
    page_size: PageSize = 20,
    include_archived: bool = False,
    status: Optional[str] = None,
    encounter_id: Optional[UUID] = None,
    search: Optional[str] = None,
) -> MeasurementListResponse:
    try:
        return service.list_measurements(
            db,
            doctor=current_doctor,
            patient_id=patient_id,
            page=page,
            page_size=page_size,
            include_archived=include_archived,
            status=status,
            encounter_id=encounter_id,
            search=search,
        )
    except PatientInformationError as error:
        raise to_http_exception(error) from error


@router.get("/measurements/{record_id}", response_model=MeasurementResponse, tags=["Patient Measurements"])
def get_measurement(patient_id: UUID, record_id: UUID, current_doctor: CurrentDoctor, db: DatabaseSession) -> MeasurementResponse:
    try:
        return MeasurementResponse.model_validate(service.get_measurement(db, doctor=current_doctor, patient_id=patient_id, record_id=record_id))
    except PatientInformationError as error:
        raise to_http_exception(error) from error


@router.patch("/measurements/{record_id}", response_model=MeasurementResponse, tags=["Patient Measurements"])
def update_measurement(patient_id: UUID, record_id: UUID, data: MeasurementUpdate, current_doctor: CurrentDoctor, db: DatabaseSession) -> MeasurementResponse:
    try:
        return MeasurementResponse.model_validate(service.update_measurement(db, doctor=current_doctor, patient_id=patient_id, record_id=record_id, data=data))
    except PatientInformationError as error:
        raise to_http_exception(error) from error


@router.post("/measurements/{record_id}/archive", response_model=MeasurementResponse, tags=["Patient Measurements"])
def archive_measurement(patient_id: UUID, record_id: UUID, current_doctor: CurrentDoctor, db: DatabaseSession) -> MeasurementResponse:
    try:
        return MeasurementResponse.model_validate(service.archive_measurement(db, doctor=current_doctor, patient_id=patient_id, record_id=record_id))
    except PatientInformationError as error:
        raise to_http_exception(error) from error


@router.post("/measurements/{record_id}/restore", response_model=MeasurementResponse, tags=["Patient Measurements"])
def restore_measurement(patient_id: UUID, record_id: UUID, current_doctor: CurrentDoctor, db: DatabaseSession) -> MeasurementResponse:
    try:
        return MeasurementResponse.model_validate(service.restore_measurement(db, doctor=current_doctor, patient_id=patient_id, record_id=record_id))
    except PatientInformationError as error:
        raise to_http_exception(error) from error


@router.post("/notes", response_model=ClinicalNoteResponse, status_code=status.HTTP_201_CREATED, tags=["Patient Notes"])
def create_note(patient_id: UUID, data: ClinicalNoteCreate, current_doctor: CurrentDoctor, db: DatabaseSession) -> ClinicalNoteResponse:
    try:
        return ClinicalNoteResponse.model_validate(service.create_note(db, doctor=current_doctor, patient_id=patient_id, data=data))
    except PatientInformationError as error:
        raise to_http_exception(error) from error


@router.get("/notes", response_model=ClinicalNoteListResponse, tags=["Patient Notes"])
def list_notes(
    patient_id: UUID,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
    page: Page = 1,
    page_size: PageSize = 20,
    include_archived: bool = False,
    note_type: Optional[str] = None,
    status: Optional[str] = None,
    encounter_id: Optional[UUID] = None,
    search: Optional[str] = None,
) -> ClinicalNoteListResponse:
    try:
        return service.list_notes(
            db,
            doctor=current_doctor,
            patient_id=patient_id,
            page=page,
            page_size=page_size,
            include_archived=include_archived,
            note_type=note_type,
            status=status,
            encounter_id=encounter_id,
            search=search,
        )
    except PatientInformationError as error:
        raise to_http_exception(error) from error


@router.get("/notes/{record_id}", response_model=ClinicalNoteResponse, tags=["Patient Notes"])
def get_note(patient_id: UUID, record_id: UUID, current_doctor: CurrentDoctor, db: DatabaseSession) -> ClinicalNoteResponse:
    try:
        return ClinicalNoteResponse.model_validate(service.get_note(db, doctor=current_doctor, patient_id=patient_id, record_id=record_id))
    except PatientInformationError as error:
        raise to_http_exception(error) from error


@router.patch("/notes/{record_id}", response_model=ClinicalNoteResponse, tags=["Patient Notes"])
def update_note(patient_id: UUID, record_id: UUID, data: ClinicalNoteUpdate, current_doctor: CurrentDoctor, db: DatabaseSession) -> ClinicalNoteResponse:
    try:
        return ClinicalNoteResponse.model_validate(service.update_note(db, doctor=current_doctor, patient_id=patient_id, record_id=record_id, data=data))
    except PatientInformationError as error:
        raise to_http_exception(error) from error


@router.post("/notes/{record_id}/archive", response_model=ClinicalNoteResponse, tags=["Patient Notes"])
def archive_note(patient_id: UUID, record_id: UUID, current_doctor: CurrentDoctor, db: DatabaseSession) -> ClinicalNoteResponse:
    try:
        return ClinicalNoteResponse.model_validate(service.archive_note(db, doctor=current_doctor, patient_id=patient_id, record_id=record_id))
    except PatientInformationError as error:
        raise to_http_exception(error) from error


@router.post("/notes/{record_id}/restore", response_model=ClinicalNoteResponse, tags=["Patient Notes"])
def restore_note(patient_id: UUID, record_id: UUID, current_doctor: CurrentDoctor, db: DatabaseSession) -> ClinicalNoteResponse:
    try:
        return ClinicalNoteResponse.model_validate(service.restore_note(db, doctor=current_doctor, patient_id=patient_id, record_id=record_id))
    except PatientInformationError as error:
        raise to_http_exception(error) from error


def to_http_exception(error: PatientInformationError) -> HTTPException:
    if isinstance(error, (PatientInformationNotFoundError, EncounterPatientMismatchError)):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        )

    if isinstance(error, (FinalClinicalNoteImmutableError, ClinicalRecordConflictError)):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        )

    if isinstance(error, (InvalidClinicalValueError, InvalidClinicalDateRangeError, InvalidObservationValueError)):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        )

    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Clinical information request failed.",
    )
