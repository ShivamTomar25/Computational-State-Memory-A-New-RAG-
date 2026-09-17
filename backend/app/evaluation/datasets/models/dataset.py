from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BenchmarkDataset(Base):
    __tablename__ = "benchmark_datasets"
    __table_args__ = (
        UniqueConstraint("name", "version", "split", name="uq_benchmark_dataset_version_split"),
        Index("ix_benchmark_datasets_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    split: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    case_count: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class BenchmarkCase(Base):
    __tablename__ = "benchmark_cases"
    __table_args__ = (
        UniqueConstraint("dataset_id", "case_key", name="uq_benchmark_case_key"),
        Index("ix_benchmark_cases_dataset", "dataset_id"),
        Index("ix_benchmark_cases_family", "scenario_family"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    dataset_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("benchmark_datasets.id", ondelete="CASCADE"), nullable=False)
    case_key: Mapped[str] = mapped_column(String(160), nullable=False)
    scenario_family: Mapped[str] = mapped_column(String(120), nullable=False)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    manifest: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class BenchmarkEvent(Base):
    __tablename__ = "benchmark_events"
    __table_args__ = (
        UniqueConstraint("case_id", "sequence_number", name="uq_benchmark_event_sequence"),
        Index("ix_benchmark_events_case", "case_id"),
        Index("ix_benchmark_events_time", "valid_time", "ingestion_time"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("benchmark_cases.id", ondelete="CASCADE"), nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    valid_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingestion_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    source_fixture: Mapped[Optional[str]] = mapped_column(String(240), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class BenchmarkQuestion(Base):
    __tablename__ = "benchmark_questions"
    __table_args__ = (
        UniqueConstraint("case_id", "turn_number", name="uq_benchmark_question_turn"),
        Index("ix_benchmark_questions_case", "case_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("benchmark_cases.id", ondelete="CASCADE"), nullable=False)
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[str] = mapped_column(String(80), nullable=False)
    expected_decision_type: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    source_cutoff: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
