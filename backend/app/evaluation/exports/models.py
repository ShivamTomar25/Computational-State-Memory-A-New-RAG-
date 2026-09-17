from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EvaluationExport(Base):
    __tablename__ = "evaluation_exports"
    __table_args__ = (
        Index("ix_evaluation_exports_experiment", "experiment_id"),
        Index("ix_evaluation_exports_type", "export_type"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    experiment_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False)
    export_type: Mapped[str] = mapped_column(String(80), nullable=False)
    object_path: Mapped[str] = mapped_column(String(500), nullable=False)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
