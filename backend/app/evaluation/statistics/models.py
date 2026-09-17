from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class StatisticalResult(Base):
    __tablename__ = "statistical_results"
    __table_args__ = (
        Index("ix_statistical_results_experiment_metric", "experiment_id", "metric_name"),
        Index("ix_statistical_results_pair", "system_a", "system_b"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    experiment_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(120), nullable=False)
    system_a: Mapped[str] = mapped_column(String(80), nullable=False)
    system_b: Mapped[str] = mapped_column(String(80), nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    test_name: Mapped[str] = mapped_column(String(120), nullable=False)
    statistic: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    raw_p_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    corrected_p_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    effect_size: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence_interval: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
