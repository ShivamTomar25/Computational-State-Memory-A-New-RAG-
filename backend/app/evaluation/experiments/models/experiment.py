from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Experiment(Base):
    __tablename__ = "experiments"
    __table_args__ = (
        Index("ix_experiments_doctor_status", "requested_by_doctor_id", "status"),
        Index("ix_experiments_dataset", "dataset_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    dataset_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("benchmark_datasets.id", ondelete="RESTRICT"), nullable=False)
    profile: Mapped[str] = mapped_column(String(40), nullable=False)
    configuration: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    comparable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requested_by_doctor_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("doctors.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class ExperimentSystemRun(Base):
    __tablename__ = "experiment_system_runs"
    __table_args__ = (
        UniqueConstraint("experiment_id", "case_id", "system_type", "repetition_number", name="uq_experiment_system_run"),
        Index("ix_system_runs_experiment", "experiment_id"),
        Index("ix_system_runs_system", "system_type", "status"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    experiment_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("benchmark_cases.id", ondelete="RESTRICT"), nullable=False)
    system_type: Mapped[str] = mapped_column(String(80), nullable=False)
    repetition_number: Mapped[int] = mapped_column(Integer, nullable=False)
    system_instance_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    conversation_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    source_cutoff: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    source_snapshot_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    configuration_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class ExperimentTurn(Base):
    __tablename__ = "experiment_turns"
    __table_args__ = (
        UniqueConstraint("system_run_id", "question_id", name="uq_experiment_turn_question"),
        Index("ix_experiment_turns_run", "system_run_id"),
        Index("ix_experiment_turns_question", "question_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    system_run_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("experiment_system_runs.id", ondelete="CASCADE"), nullable=False)
    question_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("benchmark_questions.id", ondelete="RESTRICT"), nullable=False)
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False)
    user_message_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    assistant_message_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    retrieval_run_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    llm_call_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("llm_calls.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class ExperimentOutput(Base):
    __tablename__ = "experiment_outputs"
    __table_args__ = (
        UniqueConstraint("turn_id", name="uq_experiment_output_turn"),
        Index("ix_experiment_outputs_turn", "turn_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    turn_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("experiment_turns.id", ondelete="CASCADE"), nullable=False)
    answer_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    structured_answer: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    answer_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    insufficient_evidence: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    citations: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    conflicts: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ExperimentClaim(Base):
    __tablename__ = "experiment_claims"
    __table_args__ = (
        Index("ix_experiment_claims_output", "output_id"),
        Index("ix_experiment_claims_status", "source_support_status"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    output_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("experiment_outputs.id", ondelete="CASCADE"), nullable=False)
    claim_id: Mapped[str] = mapped_column(String(120), nullable=False)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_claim: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    citation_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    source_support_status: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
