from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EncounterCreate(BaseModel):
    encounter_type: str = Field(default="outpatient", max_length=40)
    status: str = Field(default="planned", max_length=40)
    started_at: datetime
    ended_at: Optional[datetime] = None
    chief_complaint: Optional[str] = Field(default=None, max_length=4000)
    summary: Optional[str] = Field(default=None, max_length=8000)
    location: Optional[str] = Field(default=None, max_length=200)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_dates(self):
        if self.ended_at is not None and self.ended_at < self.started_at:
            raise ValueError("Encounter end time cannot be before start time.")
        return self


class EncounterUpdate(BaseModel):
    encounter_type: Optional[str] = Field(default=None, max_length=40)
    status: Optional[str] = Field(default=None, max_length=40)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    chief_complaint: Optional[str] = Field(default=None, max_length=4000)
    summary: Optional[str] = Field(default=None, max_length=8000)
    location: Optional[str] = Field(default=None, max_length=200)

    model_config = ConfigDict(extra="forbid")


class EncounterResponse(BaseModel):
    id: UUID
    patient_id: UUID
    created_by_doctor_id: UUID
    encounter_type: str
    status: str
    started_at: datetime
    ended_at: Optional[datetime]
    chief_complaint: Optional[str]
    summary: Optional[str]
    location: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EncounterListResponse(BaseModel):
    items: list[EncounterResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ConditionCreate(BaseModel):
    encounter_id: Optional[UUID] = None
    name: str = Field(min_length=1, max_length=200)
    code: Optional[str] = Field(default=None, max_length=80)
    code_system: Optional[str] = Field(default=None, max_length=80)
    category: str = Field(default="diagnosis", max_length=40)
    clinical_status: str = Field(default="active", max_length=40)
    verification_status: str = Field(default="confirmed", max_length=40)
    severity: Optional[str] = Field(default=None, max_length=40)
    onset_date: Optional[date] = None
    resolved_date: Optional[date] = None
    notes: Optional[str] = Field(default=None, max_length=8000)
    source_type: Optional[str] = Field(default=None, max_length=40)
    source_reference: Optional[str] = Field(default=None, max_length=200)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_dates(self):
        if self.onset_date and self.resolved_date and self.resolved_date < self.onset_date:
            raise ValueError("Resolved date cannot be before onset date.")
        return self


class ConditionUpdate(BaseModel):
    encounter_id: Optional[UUID] = None
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    code: Optional[str] = Field(default=None, max_length=80)
    code_system: Optional[str] = Field(default=None, max_length=80)
    category: Optional[str] = Field(default=None, max_length=40)
    clinical_status: Optional[str] = Field(default=None, max_length=40)
    verification_status: Optional[str] = Field(default=None, max_length=40)
    severity: Optional[str] = Field(default=None, max_length=40)
    onset_date: Optional[date] = None
    resolved_date: Optional[date] = None
    notes: Optional[str] = Field(default=None, max_length=8000)
    source_type: Optional[str] = Field(default=None, max_length=40)
    source_reference: Optional[str] = Field(default=None, max_length=200)

    model_config = ConfigDict(extra="forbid")


class ConditionResponse(BaseModel):
    id: UUID
    patient_id: UUID
    created_by_doctor_id: UUID
    encounter_id: Optional[UUID]
    name: str
    code: Optional[str]
    code_system: Optional[str]
    category: str
    clinical_status: str
    verification_status: str
    severity: Optional[str]
    onset_date: Optional[date]
    resolved_date: Optional[date]
    notes: Optional[str]
    source_type: str
    source_reference: Optional[str]
    is_active: bool
    recorded_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConditionListResponse(BaseModel):
    items: list[ConditionResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class MedicationCreate(BaseModel):
    encounter_id: Optional[UUID] = None
    medication_name: str = Field(min_length=1, max_length=200)
    generic_name: Optional[str] = Field(default=None, max_length=200)
    medication_code: Optional[str] = Field(default=None, max_length=80)
    code_system: Optional[str] = Field(default=None, max_length=80)
    dosage_value: Optional[Decimal] = None
    dosage_unit: Optional[str] = Field(default=None, max_length=40)
    route: Optional[str] = Field(default=None, max_length=80)
    frequency: Optional[str] = Field(default=None, max_length=120)
    instructions: Optional[str] = Field(default=None, max_length=8000)
    reason: Optional[str] = Field(default=None, max_length=4000)
    medication_status: str = Field(default="active", max_length=40)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    prescribed_by: Optional[str] = Field(default=None, max_length=150)
    source_type: Optional[str] = Field(default=None, max_length=40)
    source_reference: Optional[str] = Field(default=None, max_length=200)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_values(self):
        if self.dosage_value is not None and self.dosage_value < 0:
            raise ValueError("Dosage value cannot be negative.")
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("Medication end date cannot be before start date.")
        return self


class MedicationUpdate(BaseModel):
    encounter_id: Optional[UUID] = None
    medication_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    generic_name: Optional[str] = Field(default=None, max_length=200)
    medication_code: Optional[str] = Field(default=None, max_length=80)
    code_system: Optional[str] = Field(default=None, max_length=80)
    dosage_value: Optional[Decimal] = None
    dosage_unit: Optional[str] = Field(default=None, max_length=40)
    route: Optional[str] = Field(default=None, max_length=80)
    frequency: Optional[str] = Field(default=None, max_length=120)
    instructions: Optional[str] = Field(default=None, max_length=8000)
    reason: Optional[str] = Field(default=None, max_length=4000)
    medication_status: Optional[str] = Field(default=None, max_length=40)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    prescribed_by: Optional[str] = Field(default=None, max_length=150)
    source_type: Optional[str] = Field(default=None, max_length=40)
    source_reference: Optional[str] = Field(default=None, max_length=200)

    model_config = ConfigDict(extra="forbid")


class MedicationResponse(BaseModel):
    id: UUID
    patient_id: UUID
    created_by_doctor_id: UUID
    encounter_id: Optional[UUID]
    medication_name: str
    generic_name: Optional[str]
    medication_code: Optional[str]
    code_system: Optional[str]
    dosage_value: Optional[Decimal]
    dosage_unit: Optional[str]
    route: Optional[str]
    frequency: Optional[str]
    instructions: Optional[str]
    reason: Optional[str]
    medication_status: str
    start_date: Optional[date]
    end_date: Optional[date]
    prescribed_by: Optional[str]
    source_type: str
    source_reference: Optional[str]
    is_active: bool
    recorded_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MedicationListResponse(BaseModel):
    items: list[MedicationResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class AllergyCreate(BaseModel):
    encounter_id: Optional[UUID] = None
    substance: str = Field(min_length=1, max_length=200)
    substance_code: Optional[str] = Field(default=None, max_length=80)
    code_system: Optional[str] = Field(default=None, max_length=80)
    allergy_type: str = Field(default="allergy", max_length=40)
    category: Optional[str] = Field(default=None, max_length=40)
    clinical_status: str = Field(default="active", max_length=40)
    verification_status: str = Field(default="confirmed", max_length=40)
    criticality: Optional[str] = Field(default=None, max_length=40)
    reaction: Optional[str] = Field(default=None, max_length=4000)
    severity: Optional[str] = Field(default=None, max_length=40)
    onset_date: Optional[date] = None
    notes: Optional[str] = Field(default=None, max_length=8000)
    source_type: Optional[str] = Field(default=None, max_length=40)
    source_reference: Optional[str] = Field(default=None, max_length=200)

    model_config = ConfigDict(extra="forbid")


class AllergyUpdate(BaseModel):
    encounter_id: Optional[UUID] = None
    substance: Optional[str] = Field(default=None, min_length=1, max_length=200)
    substance_code: Optional[str] = Field(default=None, max_length=80)
    code_system: Optional[str] = Field(default=None, max_length=80)
    allergy_type: Optional[str] = Field(default=None, max_length=40)
    category: Optional[str] = Field(default=None, max_length=40)
    clinical_status: Optional[str] = Field(default=None, max_length=40)
    verification_status: Optional[str] = Field(default=None, max_length=40)
    criticality: Optional[str] = Field(default=None, max_length=40)
    reaction: Optional[str] = Field(default=None, max_length=4000)
    severity: Optional[str] = Field(default=None, max_length=40)
    onset_date: Optional[date] = None
    notes: Optional[str] = Field(default=None, max_length=8000)
    source_type: Optional[str] = Field(default=None, max_length=40)
    source_reference: Optional[str] = Field(default=None, max_length=200)

    model_config = ConfigDict(extra="forbid")


class AllergyResponse(BaseModel):
    id: UUID
    patient_id: UUID
    created_by_doctor_id: UUID
    encounter_id: Optional[UUID]
    substance: str
    substance_code: Optional[str]
    code_system: Optional[str]
    allergy_type: str
    category: Optional[str]
    clinical_status: str
    verification_status: str
    criticality: Optional[str]
    reaction: Optional[str]
    severity: Optional[str]
    onset_date: Optional[date]
    notes: Optional[str]
    source_type: str
    source_reference: Optional[str]
    is_active: bool
    recorded_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AllergyListResponse(BaseModel):
    items: list[AllergyResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class MeasurementCreate(BaseModel):
    encounter_id: Optional[UUID] = None
    observation_name: str = Field(min_length=1, max_length=200)
    observation_code: Optional[str] = Field(default=None, max_length=80)
    code_system: Optional[str] = Field(default=None, max_length=80)
    value_numeric: Optional[Decimal] = None
    value_text: Optional[str] = Field(default=None, max_length=200)
    unit: Optional[str] = Field(default=None, max_length=40)
    reference_range_low: Optional[Decimal] = None
    reference_range_high: Optional[Decimal] = None
    interpretation: Optional[str] = Field(default=None, max_length=40)
    status: str = Field(default="final", max_length=40)
    observed_at: datetime
    source_type: Optional[str] = Field(default=None, max_length=40)
    source_reference: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = Field(default=None, max_length=8000)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_values(self):
        if self.value_numeric is None and not (self.value_text and self.value_text.strip()):
            raise ValueError("A measurement requires a numeric or text value.")
        if (
            self.reference_range_low is not None
            and self.reference_range_high is not None
            and self.reference_range_low > self.reference_range_high
        ):
            raise ValueError("Reference range low cannot exceed high.")
        return self


class MeasurementUpdate(BaseModel):
    encounter_id: Optional[UUID] = None
    observation_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    observation_code: Optional[str] = Field(default=None, max_length=80)
    code_system: Optional[str] = Field(default=None, max_length=80)
    value_numeric: Optional[Decimal] = None
    value_text: Optional[str] = Field(default=None, max_length=200)
    unit: Optional[str] = Field(default=None, max_length=40)
    reference_range_low: Optional[Decimal] = None
    reference_range_high: Optional[Decimal] = None
    interpretation: Optional[str] = Field(default=None, max_length=40)
    status: Optional[str] = Field(default=None, max_length=40)
    observed_at: Optional[datetime] = None
    source_type: Optional[str] = Field(default=None, max_length=40)
    source_reference: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = Field(default=None, max_length=8000)

    model_config = ConfigDict(extra="forbid")


class MeasurementResponse(BaseModel):
    id: UUID
    patient_id: UUID
    created_by_doctor_id: UUID
    encounter_id: Optional[UUID]
    observation_name: str
    observation_code: Optional[str]
    code_system: Optional[str]
    value_numeric: Optional[Decimal]
    value_text: Optional[str]
    unit: Optional[str]
    reference_range_low: Optional[Decimal]
    reference_range_high: Optional[Decimal]
    interpretation: Optional[str]
    status: str
    observed_at: datetime
    source_type: str
    source_reference: Optional[str]
    notes: Optional[str]
    is_active: bool
    recorded_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MeasurementListResponse(BaseModel):
    items: list[MeasurementResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ClinicalNoteCreate(BaseModel):
    encounter_id: Optional[UUID] = None
    note_type: str = Field(default="progress", max_length=40)
    title: Optional[str] = Field(default=None, max_length=200)
    content: str = Field(min_length=1, max_length=20000)
    status: str = Field(default="draft", max_length=40)
    authored_at: datetime
    source_type: Optional[str] = Field(default=None, max_length=40)
    source_reference: Optional[str] = Field(default=None, max_length=200)

    model_config = ConfigDict(extra="forbid")


class ClinicalNoteUpdate(BaseModel):
    encounter_id: Optional[UUID] = None
    note_type: Optional[str] = Field(default=None, max_length=40)
    title: Optional[str] = Field(default=None, max_length=200)
    content: Optional[str] = Field(default=None, min_length=1, max_length=20000)
    status: Optional[str] = Field(default=None, max_length=40)
    authored_at: Optional[datetime] = None
    source_type: Optional[str] = Field(default=None, max_length=40)
    source_reference: Optional[str] = Field(default=None, max_length=200)

    model_config = ConfigDict(extra="forbid")


class ClinicalNoteResponse(BaseModel):
    id: UUID
    patient_id: UUID
    created_by_doctor_id: UUID
    encounter_id: Optional[UUID]
    note_type: str
    title: Optional[str]
    content: str
    status: str
    authored_at: datetime
    source_type: str
    source_reference: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClinicalNoteListResponse(BaseModel):
    items: list[ClinicalNoteResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
