from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EvaluationMetricResult(Base):
    __tablename__ = "evaluation_metric_results"
    __table_args__ = (
        Index("ix_metric_results_experiment_metric", "experiment_id", "metric_name"),
        Index("ix_metric_results_system_run", "system_run_id"),
        Index("ix_metric_results_turn", "turn_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    experiment_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False)
    system_run_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("experiment_system_runs.id", ondelete="CASCADE"), nullable=True)
    turn_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("experiment_turns.id", ondelete="CASCADE"), nullable=True)
    metric_name: Mapped[str] = mapped_column(String(120), nullable=False)
    metric_version: Mapped[str] = mapped_column(String(40), nullable=False)
    value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    numerator: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    denominator: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    applicable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    reason_not_applicable: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    details: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
