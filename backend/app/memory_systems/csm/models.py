from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CsmEvidence(Base):
    __tablename__ = "csm_evidence"
    __table_args__ = (
        UniqueConstraint("system_instance_id", "canonical_source_id", "evidence_type", name="uq_csm_evidence_source_type"),
        Index("ix_csm_evidence_instance_active", "system_instance_id", "is_active"),
        Index("ix_csm_evidence_source", "canonical_source_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    system_instance_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("memory_system_instances.id", ondelete="CASCADE"), nullable=False)
    canonical_source_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("canonical_memory_sources.id", ondelete="CASCADE"), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(80), nullable=False)
    observation_type: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    structured_value: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    normalized_value: Mapped[Optional[str]] = mapped_column(String(220), nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    document_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    section_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    conversation_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    message_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    valid_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    recorded_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confidence: Mapped[float] = mapped_column(nullable=False)
    verification_status: Mapped[str] = mapped_column(String(50), nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(80), nullable=False)
    extractor_version: Mapped[str] = mapped_column(String(40), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CsmStateVariable(Base):
    __tablename__ = "csm_state_variables"
    __table_args__ = (
        UniqueConstraint("system_instance_id", "state_type", "state_key", name="uq_csm_state_key"),
        Index("ix_csm_state_instance_key", "system_instance_id", "state_key"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    system_instance_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("memory_system_instances.id", ondelete="CASCADE"), nullable=False)
    state_type: Mapped[str] = mapped_column(String(80), nullable=False)
    state_key: Mapped[str] = mapped_column(String(220), nullable=False)
    current_value: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    confidence: Mapped[float] = mapped_column(nullable=False)
    uncertainty: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    trend: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    prediction: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False)
    update_operator: Mapped[str] = mapped_column(String(80), nullable=False)
    last_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CsmStateHistory(Base):
    __tablename__ = "csm_state_history"
    __table_args__ = (
        UniqueConstraint("state_variable_id", "version_number", name="uq_csm_state_history_version"),
        Index("ix_csm_state_history_state", "state_variable_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    state_variable_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("csm_state_variables.id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_value: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    previous_confidence: Mapped[Optional[float]] = mapped_column(nullable=True)
    new_confidence: Mapped[float] = mapped_column(nullable=False)
    update_reason: Mapped[str] = mapped_column(String(240), nullable=False)
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    update_event_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CsmStateDependency(Base):
    __tablename__ = "csm_state_dependencies"

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    system_instance_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("memory_system_instances.id", ondelete="CASCADE"), nullable=False)
    source_state_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("csm_state_variables.id", ondelete="CASCADE"), nullable=False)
    target_state_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("csm_state_variables.id", ondelete="CASCADE"), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(80), nullable=False)
    weight: Mapped[float] = mapped_column(nullable=False)
    decay: Mapped[float] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CsmStateEvidenceLink(Base):
    __tablename__ = "csm_state_evidence_links"

    state_variable_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("csm_state_variables.id", ondelete="CASCADE"), primary_key=True)
    evidence_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("csm_evidence.id", ondelete="CASCADE"), primary_key=True)
    contribution_type: Mapped[str] = mapped_column(String(80), nullable=False)
    contribution_weight: Mapped[float] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CsmConflict(Base):
    __tablename__ = "csm_conflicts"
    __table_args__ = (Index("ix_csm_conflicts_instance_status", "system_instance_id", "status"),)

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    system_instance_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("memory_system_instances.id", ondelete="CASCADE"), nullable=False)
    evidence_a_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("csm_evidence.id", ondelete="CASCADE"), nullable=False)
    evidence_b_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("csm_evidence.id", ondelete="CASCADE"), nullable=False)
    state_variable_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("csm_state_variables.id", ondelete="SET NULL"), nullable=True)
    conflict_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    resolution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class CsmReviewRequest(Base):
    __tablename__ = "csm_review_requests"
    __table_args__ = (
        UniqueConstraint(
            "system_instance_id",
            "canonical_source_id",
            "proposed_state_type",
            name="uq_csm_review_source_state",
        ),
        Index("ix_csm_review_instance_status", "system_instance_id", "status"),
        Index("ix_csm_review_patient", "patient_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    system_instance_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("memory_system_instances.id", ondelete="CASCADE"), nullable=False)
    patient_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False)
    canonical_source_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("canonical_memory_sources.id", ondelete="CASCADE"), nullable=False)
    proposed_claim: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_state_type: Mapped[str] = mapped_column(String(80), nullable=False)
    proposed_value: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    support_status: Mapped[str] = mapped_column(String(80), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    reviewed_by: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("doctors.id", ondelete="SET NULL"), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CsmUpdateEvent(Base):
    __tablename__ = "csm_update_events"

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    system_instance_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("memory_system_instances.id", ondelete="CASCADE"), nullable=False)
    trigger_source_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    operator: Mapped[str] = mapped_column(String(80), nullable=False)
    input_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    output_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CsmActivationRun(Base):
    __tablename__ = "csm_activation_runs"
    __table_args__ = (Index("ix_csm_activation_instance", "system_instance_id"),)

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    system_instance_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("memory_system_instances.id", ondelete="CASCADE"), nullable=False)
    conversation_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    token_budget: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CsmActivationItem(Base):
    __tablename__ = "csm_activation_items"

    activation_run_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("csm_activation_runs.id", ondelete="CASCADE"), primary_key=True)
    state_variable_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("csm_state_variables.id", ondelete="CASCADE"), primary_key=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    relevance_score: Mapped[float] = mapped_column(nullable=False)
    dependency_score: Mapped[float] = mapped_column(nullable=False)
    confidence_score: Mapped[float] = mapped_column(nullable=False)
    utility_score: Mapped[float] = mapped_column(nullable=False)
    estimated_token_cost: Mapped[int] = mapped_column(Integer, nullable=False)
    selected: Mapped[bool] = mapped_column(Boolean, nullable=False)
    selection_reason: Mapped[str] = mapped_column(String(240), nullable=False)
