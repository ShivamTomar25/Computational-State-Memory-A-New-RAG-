from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class LlmCall(Base):
    __tablename__ = "llm_calls"
    __table_args__ = (
        Index("ix_llm_calls_patient_created", "patient_id", "created_at"),
        Index("ix_llm_calls_system_created", "system_instance_id", "created_at"),
        Index("ix_llm_calls_conversation_created", "conversation_id", "created_at"),
        Index("ix_llm_calls_task_status", "task_type", "request_status"),
        Index("ix_llm_calls_provider_model", "provider", "model"),
        Index("ix_llm_calls_retrieval", "retrieval_run_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    patient_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("patients.id", ondelete="SET NULL"), nullable=True)
    system_instance_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("memory_system_instances.id", ondelete="SET NULL"), nullable=True)
    conversation_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    retrieval_run_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    ingestion_run_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    task_type: Mapped[str] = mapped_column(String(120), nullable=False)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    model: Mapped[str] = mapped_column(String(160), nullable=False)
    prompt_id: Mapped[str] = mapped_column(String(160), nullable=False)
    prompt_version: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    request_status: Mapped[str] = mapped_column(String(50), nullable=False)
    input_token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    finish_reason: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    error_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    data_egress_mode: Mapped[str] = mapped_column(String(80), nullable=False)
    safe_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class AnswerClaim(Base):
    __tablename__ = "answer_claims"
    __table_args__ = (
        Index("ix_answer_claims_message", "answer_message_id"),
        Index("ix_answer_claims_llm_call", "llm_call_id"),
        Index("ix_answer_claims_patient", "patient_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    system_instance_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("memory_system_instances.id", ondelete="CASCADE"), nullable=False)
    conversation_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False)
    answer_message_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False)
    llm_call_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("llm_calls.id", ondelete="SET NULL"), nullable=True)
    claim_id: Mapped[str] = mapped_column(String(120), nullable=False)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[Optional[str]] = mapped_column(String(240), nullable=True)
    predicate: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    value: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    normalized_value: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    negation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    valid_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    uncertainty: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    citation_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    source_support_status: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
