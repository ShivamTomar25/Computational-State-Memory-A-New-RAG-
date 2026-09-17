from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class GraphRagTextUnit(Base):
    __tablename__ = "graph_rag_text_units"
    __table_args__ = (Index("ix_graph_text_units_instance", "system_instance_id", "is_active"),)

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    system_instance_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("memory_system_instances.id", ondelete="CASCADE"), nullable=False)
    canonical_source_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("canonical_memory_sources.id", ondelete="CASCADE"), nullable=False)
    text_unit_text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_text_unit_id: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class GraphRagEntity(Base):
    __tablename__ = "graph_rag_entities"
    __table_args__ = (Index("ix_graph_entities_instance_name", "system_instance_id", "normalized_name"),)

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    system_instance_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("memory_system_instances.id", ondelete="CASCADE"), nullable=False)
    provider_entity_id: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    name: Mapped[str] = mapped_column(String(220), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(220), nullable=False)
    entity_type: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description_embedding_id: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    rank: Mapped[Optional[float]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class GraphRagRelationship(Base):
    __tablename__ = "graph_rag_relationships"
    __table_args__ = (Index("ix_graph_relationships_instance", "system_instance_id"),)

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    system_instance_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("memory_system_instances.id", ondelete="CASCADE"), nullable=False)
    source_entity_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("graph_rag_entities.id", ondelete="CASCADE"), nullable=True)
    target_entity_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("graph_rag_entities.id", ondelete="CASCADE"), nullable=True)
    relationship_type: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    weight: Mapped[Optional[float]] = mapped_column(nullable=True)
    provider_relationship_id: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class GraphRagClaim(Base):
    __tablename__ = "graph_rag_claims"
    __table_args__ = (Index("ix_graph_claims_instance", "system_instance_id"),)

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    system_instance_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("memory_system_instances.id", ondelete="CASCADE"), nullable=False)
    subject: Mapped[Optional[str]] = mapped_column(String(220), nullable=True)
    object: Mapped[Optional[str]] = mapped_column(String(220), nullable=True)
    claim_type: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    provider_claim_id: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)


class GraphRagSourceLink(Base):
    __tablename__ = "graph_rag_source_links"
    __table_args__ = (Index("ix_graph_source_links_source", "canonical_source_id"),)

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    system_instance_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("memory_system_instances.id", ondelete="CASCADE"), nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False)
    canonical_source_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("canonical_memory_sources.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    section_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)


class GraphRagCommunity(Base):
    __tablename__ = "graph_rag_communities"
    __table_args__ = (Index("ix_graph_communities_instance", "system_instance_id"),)

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    system_instance_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("memory_system_instances.id", ondelete="CASCADE"), nullable=False)
    provider_community_id: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(220), nullable=True)
    member_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class GraphRagCommunityReport(Base):
    __tablename__ = "graph_rag_community_reports"

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    community_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("graph_rag_communities.id", ondelete="CASCADE"), nullable=False)
    report_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    report_status: Mapped[str] = mapped_column(String(50), nullable=False)
    rank: Mapped[Optional[float]] = mapped_column(nullable=True)
    provider_model: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)


class GraphRagArtifact(Base):
    __tablename__ = "graph_rag_artifacts"
    __table_args__ = (Index("ix_graph_artifacts_instance", "system_instance_id"),)

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    system_instance_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("memory_system_instances.id", ondelete="CASCADE"), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(80), nullable=False)
    storage_object_path: Mapped[str] = mapped_column(String(512), nullable=False)
    checksum: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    provider_version: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    safe_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
