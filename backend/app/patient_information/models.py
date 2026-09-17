from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ClinicalEncounter(Base):
    __tablename__ = "clinical_encounters"
    __table_args__ = (
        Index("ix_clinical_encounters_patient_active", "patient_id", "is_active"),
        Index("ix_clinical_encounters_patient_started", "patient_id", "started_at"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_by_doctor_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("doctors.id", ondelete="RESTRICT"), nullable=False, index=True)
    encounter_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    chief_complaint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class MedicalCondition(Base):
    __tablename__ = "clinical_conditions"
    __table_args__ = (
        Index("ix_clinical_conditions_patient_active", "patient_id", "is_active"),
        Index("ix_clinical_conditions_patient_status", "patient_id", "clinical_status"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_by_doctor_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("doctors.id", ondelete="RESTRICT"), nullable=False, index=True)
    encounter_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("clinical_encounters.id", ondelete="RESTRICT"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    code_system: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    clinical_status: Mapped[str] = mapped_column(String(40), nullable=False)
    verification_status: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    onset_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    resolved_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_reference: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Medication(Base):
    __tablename__ = "clinical_medications"
    __table_args__ = (
        Index("ix_clinical_medications_patient_active", "patient_id", "is_active"),
        Index("ix_clinical_medications_patient_status", "patient_id", "medication_status"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_by_doctor_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("doctors.id", ondelete="RESTRICT"), nullable=False, index=True)
    encounter_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("clinical_encounters.id", ondelete="RESTRICT"), nullable=True, index=True)
    medication_name: Mapped[str] = mapped_column(String(200), nullable=False)
    generic_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    medication_code: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    code_system: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    dosage_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    dosage_unit: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    route: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    frequency: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    medication_status: Mapped[str] = mapped_column(String(40), nullable=False)
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    prescribed_by: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_reference: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Allergy(Base):
    __tablename__ = "clinical_allergies"
    __table_args__ = (
        Index("ix_clinical_allergies_patient_active", "patient_id", "is_active"),
        Index("ix_clinical_allergies_patient_status", "patient_id", "clinical_status"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_by_doctor_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("doctors.id", ondelete="RESTRICT"), nullable=False, index=True)
    encounter_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("clinical_encounters.id", ondelete="RESTRICT"), nullable=True, index=True)
    substance: Mapped[str] = mapped_column(String(200), nullable=False)
    substance_code: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    code_system: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    allergy_type: Mapped[str] = mapped_column(String(40), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    clinical_status: Mapped[str] = mapped_column(String(40), nullable=False)
    verification_status: Mapped[str] = mapped_column(String(40), nullable=False)
    criticality: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    reaction: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    severity: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    onset_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_reference: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Measurement(Base):
    __tablename__ = "clinical_measurements"
    __table_args__ = (
        Index("ix_clinical_measurements_patient_active", "patient_id", "is_active"),
        Index("ix_clinical_measurements_patient_observed", "patient_id", "observed_at"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_by_doctor_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("doctors.id", ondelete="RESTRICT"), nullable=False, index=True)
    encounter_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("clinical_encounters.id", ondelete="RESTRICT"), nullable=True, index=True)
    observation_name: Mapped[str] = mapped_column(String(200), nullable=False)
    observation_code: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    code_system: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    value_numeric: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 4), nullable=True)
    value_text: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    reference_range_low: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 4), nullable=True)
    reference_range_high: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 4), nullable=True)
    interpretation: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_reference: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ClinicalNote(Base):
    __tablename__ = "clinical_notes"
    __table_args__ = (
        Index("ix_clinical_notes_patient_active", "patient_id", "is_active"),
        Index("ix_clinical_notes_patient_authored", "patient_id", "authored_at"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_by_doctor_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("doctors.id", ondelete="RESTRICT"), nullable=False, index=True)
    encounter_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("clinical_encounters.id", ondelete="RESTRICT"), nullable=True, index=True)
    note_type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    authored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_reference: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
