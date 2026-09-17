from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MemorySystemInstance(Base):
    __tablename__ = "memory_system_instances"
    __table_args__ = (
        UniqueConstraint("patient_id", "system_type", name="uq_memory_instances_patient_system"),
        Index("ix_memory_instances_patient", "patient_id"),
        Index("ix_memory_instances_system_status", "system_type", "status"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False)
    system_type: Mapped[str] = mapped_column(String(80), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    capability_status: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    configuration: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    pipeline_version: Mapped[int] = mapped_column(Integer, nullable=False)
    initialized_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    source_cutoff_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_code: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CanonicalMemorySource(Base):
    __tablename__ = "canonical_memory_sources"
    __table_args__ = (
        UniqueConstraint(
            "patient_id",
            "source_type",
            "source_subtype",
            "source_record_id",
            "source_version",
            "visibility_scope",
            "owning_system_instance_id",
            name="uq_canonical_source_version",
        ),
        CheckConstraint(
            "(visibility_scope = 'patient_shared' AND owning_system_instance_id IS NULL) OR "
            "(visibility_scope = 'system_private' AND owning_system_instance_id IS NOT NULL)",
            name="ck_canonical_visibility_owner",
        ),
        Index("ix_canonical_patient_visibility", "patient_id", "visibility_scope"),
        Index("ix_canonical_patient_source", "patient_id", "source_type"),
        Index("ix_canonical_owner", "owning_system_instance_id"),
        Index("ix_canonical_document", "document_id"),
        Index("ix_canonical_conversation", "conversation_id"),
        Index("ix_canonical_content_hash", "content_hash"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_subtype: Mapped[str] = mapped_column(String(80), nullable=False)
    source_record_id: Mapped[str] = mapped_column(String(120), nullable=False)
    source_version: Mapped[str] = mapped_column(String(160), nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    structured_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    recorded_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    document_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    section_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("document_sections.id", ondelete="SET NULL"), nullable=True)
    encounter_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("clinical_encounters.id", ondelete="SET NULL"), nullable=True)
    conversation_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    message_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    role: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    owning_system_instance_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("memory_system_instances.id", ondelete="CASCADE"), nullable=True)
    visibility_scope: Mapped[str] = mapped_column(String(40), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class MemorySystemSourceLink(Base):
    __tablename__ = "memory_system_source_links"
    __table_args__ = (
        UniqueConstraint(
            "system_instance_id",
            "canonical_source_id",
            "source_hash",
            name="uq_memory_source_link_version",
        ),
        Index("ix_memory_source_links_instance", "system_instance_id"),
        Index("ix_memory_source_links_source", "canonical_source_id"),
        Index("ix_memory_source_links_status", "ingestion_status"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    system_instance_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("memory_system_instances.id", ondelete="CASCADE"), nullable=False)
    canonical_source_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("canonical_memory_sources.id", ondelete="CASCADE"), nullable=False)
    native_record_type: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    native_record_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    source_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    ingestion_status: Mapped[str] = mapped_column(String(50), nullable=False)
    indexed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deactivated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class MemoryIngestionRun(Base):
    __tablename__ = "memory_ingestion_runs"
    __table_args__ = (
        Index("ix_memory_ingestion_instance_status", "system_instance_id", "status"),
        Index("ix_memory_ingestion_instance_created", "system_instance_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    system_instance_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("memory_system_instances.id", ondelete="CASCADE"), nullable=False)
    patient_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False)
    mode: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    cutoff_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    pipeline_version: Mapped[int] = mapped_column(Integer, nullable=False)
    configuration_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    source_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_code: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class MemoryIngestionRunItem(Base):
    __tablename__ = "memory_ingestion_run_items"
    __table_args__ = (
        Index("ix_memory_run_items_run", "run_id"),
        Index("ix_memory_run_items_source", "canonical_source_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("memory_ingestion_runs.id", ondelete="CASCADE"), nullable=False)
    canonical_source_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("canonical_memory_sources.id", ondelete="CASCADE"), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    native_record_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    failure_code: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class MemoryConversation(Base):
    __tablename__ = "memory_conversations"
    __table_args__ = (
        Index("ix_memory_conversations_instance_updated", "system_instance_id", "updated_at"),
        Index("ix_memory_conversations_patient_system", "patient_id", "system_type"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False)
    doctor_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("doctors.id", ondelete="RESTRICT"), nullable=False)
    system_instance_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("memory_system_instances.id", ondelete="CASCADE"), nullable=False)
    system_type: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(220), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_message_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class MemoryMessage(Base):
    __tablename__ = "memory_messages"
    __table_args__ = (
        UniqueConstraint("conversation_id", "sequence_number", name="uq_memory_message_sequence"),
        Index("ix_memory_messages_conversation_sequence", "conversation_id", "sequence_number"),
        Index("ix_memory_messages_instance", "system_instance_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("memory_conversations.id", ondelete="CASCADE"), nullable=False)
    patient_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False)
    system_instance_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("memory_system_instances.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    generation_status: Mapped[str] = mapped_column(String(50), nullable=False)
    retrieval_run_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MemoryRetrievalRun(Base):
    __tablename__ = "memory_retrieval_runs"
    __table_args__ = (
        Index("ix_memory_retrieval_instance_created", "system_instance_id", "created_at"),
        Index("ix_memory_retrieval_patient", "patient_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    system_instance_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("memory_system_instances.id", ondelete="CASCADE"), nullable=False)
    patient_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False)
    conversation_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    retrieval_mode: Mapped[str] = mapped_column(String(80), nullable=False)
    requested_top_k: Mapped[int] = mapped_column(Integer, nullable=False)
    requested_token_budget: Mapped[int] = mapped_column(Integer, nullable=False)
    result_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    configuration_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MemoryRetrievalItem(Base):
    __tablename__ = "memory_retrieval_items"
    __table_args__ = (
        Index("ix_memory_retrieval_items_run_rank", "retrieval_run_id", "rank"),
        Index("ix_memory_retrieval_items_source", "canonical_source_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    retrieval_run_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("memory_retrieval_runs.id", ondelete="CASCADE"), nullable=False)
    canonical_source_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("canonical_memory_sources.id", ondelete="SET NULL"), nullable=True)
    system_native_type: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    system_native_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    normalized_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    dense_rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    lexical_rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    graph_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    source_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    document_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    section_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    content_preview: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MemorySystemEvent(Base):
    __tablename__ = "memory_system_events"
    __table_args__ = (
        Index("ix_memory_events_instance_created", "system_instance_id", "created_at"),
        Index("ix_memory_events_patient", "patient_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    system_instance_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("memory_system_instances.id", ondelete="CASCADE"), nullable=False)
    patient_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    safe_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    request_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
