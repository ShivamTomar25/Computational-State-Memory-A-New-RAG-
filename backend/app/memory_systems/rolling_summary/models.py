from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RollingSummarySnapshot(Base):
    __tablename__ = "rolling_summary_snapshots"
    __table_args__ = (
        UniqueConstraint("system_instance_id", "version_number", name="uq_rolling_summary_version"),
        Index("ix_rolling_summary_instance", "system_instance_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    system_instance_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("memory_system_instances.id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    summary_status: Mapped[str] = mapped_column(String(50), nullable=False)
    covered_cutoff_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    input_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    source_count: Mapped[int] = mapped_column(Integer, nullable=False)
    summarizer_provider: Mapped[str] = mapped_column(String(120), nullable=False)
    summarizer_model: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RollingSummaryCoverage(Base):
    __tablename__ = "rolling_summary_coverage"
    __table_args__ = (UniqueConstraint("snapshot_id", "canonical_source_id", name="uq_rolling_coverage_source"),)

    snapshot_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("rolling_summary_snapshots.id", ondelete="CASCADE"), primary_key=True)
    canonical_source_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("canonical_memory_sources.id", ondelete="CASCADE"), primary_key=True)
    covered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RollingSummaryRecentItem(Base):
    __tablename__ = "rolling_summary_recent_items"
    __table_args__ = (Index("ix_rolling_recent_instance_active", "system_instance_id", "is_active"),)

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    system_instance_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("memory_system_instances.id", ondelete="CASCADE"), nullable=False)
    canonical_source_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("canonical_memory_sources.id", ondelete="CASCADE"), nullable=False)
    content_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class RollingSummaryPendingInput(Base):
    __tablename__ = "rolling_summary_pending_inputs"
    __table_args__ = (
        UniqueConstraint("system_instance_id", "canonical_source_id", name="uq_rolling_pending_source"),
        Index("ix_rolling_pending_instance", "system_instance_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    system_instance_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("memory_system_instances.id", ondelete="CASCADE"), nullable=False)
    canonical_source_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("canonical_memory_sources.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
