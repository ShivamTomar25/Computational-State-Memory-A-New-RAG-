from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class HippoPassageNode(Base):
    __tablename__ = "hippo_passage_nodes"
    __table_args__ = (Index("ix_hippo_passages_instance", "system_instance_id", "is_active"),)

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    system_instance_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("memory_system_instances.id", ondelete="CASCADE"), nullable=False)
    canonical_source_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("canonical_memory_sources.id", ondelete="CASCADE"), nullable=False)
    passage_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_id: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_node_id: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class HippoEntityNode(Base):
    __tablename__ = "hippo_entity_nodes"
    __table_args__ = (Index("ix_hippo_entities_instance_name", "system_instance_id", "normalized_name"),)

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    system_instance_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("memory_system_instances.id", ondelete="CASCADE"), nullable=False)
    entity_name: Mapped[str] = mapped_column(String(220), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(220), nullable=False)
    entity_type: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    embedding_id: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    provider_node_id: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)


class HippoFactEdge(Base):
    __tablename__ = "hippo_fact_edges"

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    system_instance_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("memory_system_instances.id", ondelete="CASCADE"), nullable=False)
    subject_node_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    predicate: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    object_node_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    source_passage_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("hippo_passage_nodes.id", ondelete="CASCADE"), nullable=True)
    edge_weight: Mapped[Optional[float]] = mapped_column(nullable=True)
    provider_edge_id: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)


class HippoPassageEntityEdge(Base):
    __tablename__ = "hippo_passage_entity_edges"

    passage_node_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("hippo_passage_nodes.id", ondelete="CASCADE"), primary_key=True)
    entity_node_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("hippo_entity_nodes.id", ondelete="CASCADE"), primary_key=True)
    edge_type: Mapped[str] = mapped_column(String(80), nullable=False)
    weight: Mapped[float] = mapped_column(nullable=False)


class HippoSynonymEdge(Base):
    __tablename__ = "hippo_synonym_edges"

    source_entity_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("hippo_entity_nodes.id", ondelete="CASCADE"), primary_key=True)
    target_entity_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("hippo_entity_nodes.id", ondelete="CASCADE"), primary_key=True)
    similarity: Mapped[float] = mapped_column(nullable=False)
    provider_edge_id: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)


class HippoIndexRun(Base):
    __tablename__ = "hippo_index_runs"
    __table_args__ = (Index("ix_hippo_index_runs_instance", "system_instance_id"),)

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    system_instance_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("memory_system_instances.id", ondelete="CASCADE"), nullable=False)
    provider_version: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    openie_provider: Mapped[str] = mapped_column(String(120), nullable=False)
    embedding_configuration: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    ppr_configuration: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    source_cutoff_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class HippoRetrievalTrace(Base):
    __tablename__ = "hippo_retrieval_traces"
    __table_args__ = (Index("ix_hippo_traces_instance", "system_instance_id"),)

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    system_instance_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("memory_system_instances.id", ondelete="CASCADE"), nullable=False)
    retrieval_run_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("memory_retrieval_runs.id", ondelete="CASCADE"), nullable=True)
    query_entities: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    seed_nodes: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    ppr_parameters: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    activated_nodes: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    passage_ranks: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    scores: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
