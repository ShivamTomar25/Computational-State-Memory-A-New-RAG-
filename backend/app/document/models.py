from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("size_bytes_expected > 0", name="ck_documents_expected_size_positive"),
        CheckConstraint("size_bytes_actual IS NULL OR size_bytes_actual >= 0", name="ck_documents_actual_size_non_negative"),
        CheckConstraint("version_number > 0", name="ck_documents_version_positive"),
        UniqueConstraint("storage_object_path", name="uq_documents_storage_object_path"),
        Index("ix_documents_patient_active", "patient_id", "is_active"),
        Index("ix_documents_patient_created", "patient_id", "created_at"),
        Index("ix_documents_patient_type", "patient_id", "document_type"),
        Index("ix_documents_patient_processing_status", "patient_id", "processing_status"),
        Index("ix_documents_uploaded_by_doctor", "uploaded_by_doctor_id"),
        Index("ix_documents_checksum_actual", "checksum_actual"),
        Index("ix_documents_encounter", "encounter_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False, index=True)
    uploaded_by_doctor_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("doctors.id", ondelete="RESTRICT"), nullable=False)
    encounter_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("clinical_encounters.id", ondelete="RESTRICT"), nullable=True)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(220), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    safe_filename: Mapped[str] = mapped_column(String(160), nullable=False)
    file_extension: Mapped[str] = mapped_column(String(20), nullable=False)
    declared_content_type: Mapped[str] = mapped_column(String(160), nullable=False)
    detected_content_type: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    size_bytes_expected: Mapped[int] = mapped_column(Integer, nullable=False)
    size_bytes_actual: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    checksum_algorithm: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    checksum_expected: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    checksum_actual: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    duplicate_of_document_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("documents.id", ondelete="RESTRICT"), nullable=True)
    storage_provider: Mapped[str] = mapped_column(String(40), nullable=False)
    storage_bucket: Mapped[str] = mapped_column(String(120), nullable=False)
    storage_object_path: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_object_version: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    storage_etag: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    document_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    upload_status: Mapped[str] = mapped_column(String(50), nullable=False)
    verification_status: Mapped[str] = mapped_column(String(50), nullable=False)
    processing_status: Mapped[str] = mapped_column(String(50), nullable=False)
    text_extraction_status: Mapped[str] = mapped_column(String(50), nullable=False)
    ocr_requirement_status: Mapped[str] = mapped_column(String(50), nullable=False)
    failure_code: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    replaces_document_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("documents.id", ondelete="RESTRICT"), nullable=True)
    superseded_by_document_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("documents.id", ondelete="RESTRICT"), nullable=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_current_version: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    upload_deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    uploaded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class DocumentText(Base):
    __tablename__ = "document_texts"
    __table_args__ = (
        UniqueConstraint("document_id", name="uq_document_texts_document_id"),
        Index("ix_document_texts_document", "document_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(80), nullable=False)
    extractor_name: Mapped[str] = mapped_column(String(120), nullable=False)
    extractor_version: Mapped[str] = mapped_column(String(40), nullable=False)
    raw_text_object_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    normalized_text_object_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    normalized_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    character_count: Mapped[int] = mapped_column(Integer, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False)
    detected_language: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    quality_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    quality_status: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class DocumentPage(Base):
    __tablename__ = "document_pages"
    __table_args__ = (
        UniqueConstraint("document_id", "page_number", name="uq_document_pages_document_page"),
        Index("ix_document_pages_document_page", "document_id", "page_number"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    character_count: Mapped[int] = mapped_column(Integer, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False)
    text_quality_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    has_text: Mapped[bool] = mapped_column(Boolean, nullable=False)
    likely_requires_ocr: Mapped[bool] = mapped_column(Boolean, nullable=False)
    extraction_status: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class DocumentSection(Base):
    __tablename__ = "document_sections"
    __table_args__ = (
        UniqueConstraint("document_id", "section_index", name="uq_document_sections_document_section"),
        Index("ix_document_sections_document_section", "document_id", "section_index"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    section_index: Mapped[int] = mapped_column(Integer, nullable=False)
    heading: Mapped[Optional[str]] = mapped_column(String(220), nullable=True)
    section_type: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    page_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    page_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    extraction_method: Mapped[str] = mapped_column(String(80), nullable=False)
    confidence: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class DocumentArtifact(Base):
    __tablename__ = "document_artifacts"
    __table_args__ = (
        UniqueConstraint("storage_object_path", name="uq_document_artifacts_storage_object_path"),
        Index("ix_document_artifacts_document", "document_id"),
        Index("ix_document_artifacts_storage_object_path", "storage_object_path"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(80), nullable=False)
    storage_provider: Mapped[str] = mapped_column(String(40), nullable=False)
    storage_bucket: Mapped[str] = mapped_column(String(120), nullable=False)
    storage_object_path: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_object_version: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    content_type: Mapped[str] = mapped_column(String(160), nullable=False)
    size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    checksum: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    processor_name: Mapped[str] = mapped_column(String(120), nullable=False)
    processor_version: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DocumentProcessingJob(Base):
    __tablename__ = "document_processing_jobs"
    __table_args__ = (
        Index("ix_document_processing_jobs_document", "document_id"),
        Index("ix_document_processing_jobs_status", "status"),
        Index("ix_document_processing_jobs_next_retry", "next_retry_at"),
        Index("ix_document_processing_jobs_queued", "queued_at"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    patient_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False)
    job_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_code: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    worker_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    input_version: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    processor_name: Mapped[str] = mapped_column(String(120), nullable=False)
    processor_version: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class DocumentProcessingRun(Base):
    __tablename__ = "document_processing_runs"
    __table_args__ = (
        Index("ix_document_processing_runs_document", "document_id"),
        Index("ix_document_processing_runs_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    pipeline_version: Mapped[int] = mapped_column(Integer, nullable=False)
    input_checksum: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    input_object_version: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    extractor_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    extractor_version: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    quality_status: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    ocr_requirement_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    failure_code: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DocumentAuditEvent(Base):
    __tablename__ = "document_audit_events"
    __table_args__ = (
        Index("ix_document_audit_document_created", "document_id", "created_at"),
        Index("ix_document_audit_patient_created", "patient_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    patient_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False)
    doctor_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("doctors.id", ondelete="RESTRICT"), nullable=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(40), nullable=False)
    request_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
