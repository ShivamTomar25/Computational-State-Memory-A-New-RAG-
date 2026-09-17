from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class HybridRagChunk(Base):
    __tablename__ = "hybrid_rag_chunks"
    __table_args__ = (
        UniqueConstraint("system_instance_id", "canonical_source_id", "chunk_index", "content_hash", name="uq_hybrid_chunk_source_hash"),
        Index("ix_hybrid_chunks_instance_active", "system_instance_id", "is_active"),
        Index("ix_hybrid_chunks_source", "canonical_source_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    system_instance_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("memory_system_instances.id", ondelete="CASCADE"), nullable=False)
    canonical_source_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("canonical_memory_sources.id", ondelete="CASCADE"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_subtype: Mapped[str] = mapped_column(String(80), nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    document_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    section_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    conversation_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    message_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    lexical_document: Mapped[str] = mapped_column(Text, nullable=False)
    language_config: Mapped[str] = mapped_column(String(40), nullable=False)
    dense_status: Mapped[str] = mapped_column(String(50), nullable=False)
    lexical_status: Mapped[str] = mapped_column(String(50), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(160), nullable=False)
    embedding_revision: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    embedding_vector: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class HybridRagRetrievalCandidate(Base):
    __tablename__ = "hybrid_rag_retrieval_candidates"
    __table_args__ = (Index("ix_hybrid_candidates_run", "retrieval_run_id"),)

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    retrieval_run_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("memory_retrieval_runs.id", ondelete="CASCADE"), nullable=False)
    chunk_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("hybrid_rag_chunks.id", ondelete="CASCADE"), nullable=False)
    dense_rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    dense_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    lexical_rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    lexical_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    fused_score: Mapped[float] = mapped_column(nullable=False)
