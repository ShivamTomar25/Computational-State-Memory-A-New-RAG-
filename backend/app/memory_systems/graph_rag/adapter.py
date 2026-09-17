from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.memory_systems.common.models.memory import CanonicalMemorySource
from app.memory_systems.common.registry.adapter import MemorySystemAdapter, source_preview
from app.memory_systems.common.schemas.canonical import IngestionResult
from app.memory_systems.common.schemas.memory import CapabilityStatus, MemoryContextItem
from app.memory_systems.common.token_budget.service import apply_token_budget, estimate_tokens
from app.memory_systems.graph_rag.factory import create_graphrag_provider
from app.memory_systems.graph_rag.local_index import extract_entities, lexical_score
from app.memory_systems.graph_rag.models import (
    GraphRagCommunity,
    GraphRagEntity,
    GraphRagRelationship,
    GraphRagSourceLink,
    GraphRagTextUnit,
)


class GraphRagAdapter(MemorySystemAdapter):
    system_type = "graph_rag"

    def capability_status(self) -> CapabilityStatus:
        provider = create_graphrag_provider(settings)
        provider_status = provider.provider_status()
        local_available = provider_status == "available"

        return CapabilityStatus(
            ingestion="available" if local_available else provider_status,
            retrieval="available" if local_available else "not_ready",
            conversation_memory="available",
            answer_generation="requires_llm",
            incremental_update="available" if local_available else "requires_llm",
            embeddings="available" if local_available else "requires_embeddings",
            provider=provider_status,
        )

    def configuration(self) -> dict:
        provider = create_graphrag_provider(settings)
        configuration = provider.configuration()
        configuration.update(
            {
                "artifact_storage": "supabase_private_system_artifacts",
                "retrieval_modes": ["local", "global"],
            }
        )

        return configuration

    def ingest_sources(self, db: Session, *, instance, sources: list) -> list[IngestionResult]:
        results: list[IngestionResult] = []

        for source in sources:
            text_unit = db.scalar(
                select(GraphRagTextUnit).where(
                    GraphRagTextUnit.system_instance_id == instance.id,
                    GraphRagTextUnit.canonical_source_id == source.id,
                    GraphRagTextUnit.content_hash == source.content_hash,
                )
            )

            if text_unit is None:
                text_unit = GraphRagTextUnit(
                    system_instance_id=instance.id,
                    canonical_source_id=source.id,
                    text_unit_text=source.content_text,
                    token_count=estimate_tokens(source.content_text),
                    source_type=source.source_type,
                    content_hash=source.content_hash,
                    provider_text_unit_id=None,
                    is_active=True,
                )
                db.add(text_unit)
                db.flush()
            else:
                text_unit.is_active = True

            indexed_entities = self.index_entities(db=db, instance=instance, source=source)
            self.index_relationships(db=db, instance=instance, source=source, entities=indexed_entities)
            self.index_community(db=db, instance=instance)

            results.append(
                IngestionResult(
                    native_record_type="graph_rag_text_unit",
                    native_record_id=text_unit.id,
                    canonical_source_id=source.id,
                    source_hash=source.content_hash,
                    status="indexed",
                )
            )

        return results

    def retrieve(self, db: Session, *, instance, query: str, top_k: int, token_budget: int, retrieval_mode):
        query_entities = {entity["normalized_name"] for entity in extract_entities(query, limit=12)}
        rows = list(
            db.execute(
                select(GraphRagTextUnit, CanonicalMemorySource)
                .join(CanonicalMemorySource, GraphRagTextUnit.canonical_source_id == CanonicalMemorySource.id)
                .where(
                    GraphRagTextUnit.system_instance_id == instance.id,
                    GraphRagTextUnit.is_active.is_(True),
                    CanonicalMemorySource.patient_id == instance.patient_id,
                    CanonicalMemorySource.is_active.is_(True),
                )
            ).all()
        )
        scored = []

        for text_unit, source in rows:
            text_entities = {entity["normalized_name"] for entity in extract_entities(text_unit.text_unit_text, limit=24)}
            entity_overlap = len(query_entities & text_entities)
            score = lexical_score(query, text_unit.text_unit_text) + entity_overlap
            scored.append((score, entity_overlap, text_entities, text_unit, source))

        ranked = sorted(scored, key=lambda item: item[0], reverse=True)
        items = [
            MemoryContextItem(
                rank=index + 1,
                score=score,
                source_type=source.source_type,
                source_subtype=source.source_subtype,
                content_preview=source_preview(text_unit.text_unit_text),
                content=text_unit.text_unit_text,
                canonical_source_id=source.id,
                system_native_type="graph_rag_text_unit",
                system_native_id=text_unit.id,
                document_id=source.document_id,
                page_number=source.page_number,
                section_id=source.section_id,
                conversation_id=source.conversation_id,
                message_id=source.message_id,
                event_time=source.event_time,
                token_count=text_unit.token_count,
                graph_score=score,
                metadata={
                    "matched_entity_count": entity_overlap,
                    "query_entities": sorted(query_entities),
                    "text_entities": sorted(text_entities)[:12],
                    "retrieval_mode": retrieval_mode or "local",
                },
            )
            for index, (score, entity_overlap, text_entities, text_unit, source) in enumerate(ranked)
            if score > 0
        ]
        budget = apply_token_budget(items, token_budget=token_budget)

        return budget.included[:top_k], [], "ready"

    def get_statistics(self, db: Session, *, instance) -> dict:
        text_units = db.scalar(
            select(func.count()).select_from(GraphRagTextUnit).where(
                GraphRagTextUnit.system_instance_id == instance.id,
                GraphRagTextUnit.is_active.is_(True),
            )
        )
        entities = db.scalar(
            select(func.count()).select_from(GraphRagEntity).where(GraphRagEntity.system_instance_id == instance.id)
        )
        relationships = db.scalar(
            select(func.count())
            .select_from(GraphRagRelationship)
            .where(GraphRagRelationship.system_instance_id == instance.id)
        )
        communities = db.scalar(
            select(func.count()).select_from(GraphRagCommunity).where(GraphRagCommunity.system_instance_id == instance.id)
        )

        return {
            "text_units": int(text_units or 0),
            "entities": int(entities or 0),
            "relationships": int(relationships or 0),
            "communities": int(communities or 0),
            "provider": create_graphrag_provider(settings).configuration()["provider"],
            "graph_indexing": "available",
        }

    def index_entities(self, db: Session, *, instance, source) -> list[GraphRagEntity]:
        indexed_entities = []

        for entity_data in extract_entities(source.content_text):
            entity = db.scalar(
                select(GraphRagEntity).where(
                    GraphRagEntity.system_instance_id == instance.id,
                    GraphRagEntity.normalized_name == entity_data["normalized_name"],
                )
            )

            if entity is None:
                entity = GraphRagEntity(
                    system_instance_id=instance.id,
                    provider_entity_id=None,
                    name=entity_data["name"],
                    normalized_name=entity_data["normalized_name"],
                    entity_type=entity_data["entity_type"],
                    description=f"Local graph entity extracted from {source.source_type}.",
                    description_embedding_id=None,
                    rank=float(entity_data["frequency"]),
                )
                db.add(entity)
                db.flush()
            else:
                entity.rank = float(entity.rank or 0) + float(entity_data["frequency"])

            self.link_source(db=db, instance=instance, source=source, target_type="entity", target_id=entity.id)
            indexed_entities.append(entity)

        return indexed_entities

    def index_relationships(self, db: Session, *, instance, source, entities: list[GraphRagEntity]) -> None:
        for left_index, left in enumerate(entities):
            for right in entities[left_index + 1 :]:
                relationship = db.scalar(
                    select(GraphRagRelationship).where(
                        GraphRagRelationship.system_instance_id == instance.id,
                        or_(
                            (
                                (GraphRagRelationship.source_entity_id == left.id)
                                & (GraphRagRelationship.target_entity_id == right.id)
                            ),
                            (
                                (GraphRagRelationship.source_entity_id == right.id)
                                & (GraphRagRelationship.target_entity_id == left.id)
                            ),
                        ),
                        GraphRagRelationship.relationship_type == "co_occurs",
                    )
                )

                if relationship is None:
                    relationship = GraphRagRelationship(
                        system_instance_id=instance.id,
                        source_entity_id=left.id,
                        target_entity_id=right.id,
                        relationship_type="co_occurs",
                        description=f"{left.name} and {right.name} occur in the same clinical source.",
                        weight=1.0,
                        provider_relationship_id=None,
                    )
                    db.add(relationship)
                    db.flush()
                else:
                    relationship.weight = float(relationship.weight or 0) + 1.0

                self.link_source(
                    db=db,
                    instance=instance,
                    source=source,
                    target_type="relationship",
                    target_id=relationship.id,
                )

    def index_community(self, db: Session, *, instance) -> None:
        entity_count = db.scalar(
            select(func.count()).select_from(GraphRagEntity).where(GraphRagEntity.system_instance_id == instance.id)
        )

        if not entity_count:
            return

        community = db.scalar(
            select(GraphRagCommunity).where(
                GraphRagCommunity.system_instance_id == instance.id,
                GraphRagCommunity.level == 0,
                GraphRagCommunity.title == "Clinical Evidence Graph",
            )
        )

        if community is None:
            db.add(
                GraphRagCommunity(
                    system_instance_id=instance.id,
                    provider_community_id=None,
                    level=0,
                    parent_id=None,
                    title="Clinical Evidence Graph",
                    member_count=int(entity_count),
                )
            )
        else:
            community.member_count = int(entity_count)

    def link_source(self, db: Session, *, instance, source, target_type: str, target_id) -> None:
        link = db.scalar(
            select(GraphRagSourceLink).where(
                GraphRagSourceLink.system_instance_id == instance.id,
                GraphRagSourceLink.target_type == target_type,
                GraphRagSourceLink.target_id == target_id,
                GraphRagSourceLink.canonical_source_id == source.id,
            )
        )

        if link is not None:
            return

        db.add(
            GraphRagSourceLink(
                system_instance_id=instance.id,
                target_type=target_type,
                target_id=target_id,
                canonical_source_id=source.id,
                document_id=source.document_id,
                page_number=source.page_number,
                section_id=source.section_id,
            )
        )
