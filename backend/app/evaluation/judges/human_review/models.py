from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EvaluationAnnotation(Base):
    __tablename__ = "evaluation_annotations"
    __table_args__ = (
        Index("ix_evaluation_annotations_output", "output_id"),
        Index("ix_evaluation_annotations_claim", "claim_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    output_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("experiment_outputs.id", ondelete="CASCADE"), nullable=False)
    claim_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("experiment_claims.id", ondelete="CASCADE"), nullable=True)
    reviewer_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("doctors.id", ondelete="SET NULL"), nullable=True)
    annotation_type: Mapped[str] = mapped_column(String(80), nullable=False)
    value: Mapped[str] = mapped_column(String(160), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
