from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BenchmarkGroundTruth(Base):
    __tablename__ = "benchmark_ground_truth"
    __table_args__ = (
        UniqueConstraint("question_id", "version", name="uq_ground_truth_question_version"),
        Index("ix_ground_truth_question", "question_id"),
        Index("ix_ground_truth_status", "reviewer_status"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    question_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("benchmark_questions.id", ondelete="CASCADE"), nullable=False)
    truth: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    reviewer_status: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
