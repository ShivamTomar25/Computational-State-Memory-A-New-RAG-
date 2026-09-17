from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.memory_systems.common.models.memory import CanonicalMemorySource
from app.memory_systems.common.registry.adapter import MemorySystemAdapter, source_preview
from app.memory_systems.common.schemas.canonical import IngestionResult
from app.memory_systems.common.schemas.memory import CapabilityStatus, MemoryContextItem
from app.memory_systems.common.token_budget.service import apply_token_budget
from app.memory_systems.hippo_rag.factory import create_hipporag_provider
from app.memory_systems.hippo_rag.local_index import extract_entities, passage_score
from app.memory_systems.hippo_rag.models import (
    HippoEntityNode,
    HippoFactEdge,
    HippoIndexRun,
    HippoPassageEntityEdge,
    HippoPassageNode,
)


class HippoRagAdapter(MemorySystemAdapter):
    system_type = "hippo_rag"

    def capability_status(self) -> CapabilityStatus:
        provider = create_hipporag_provider(settings)
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
        return create_hipporag_provider(settings).configuration()

    def ingest_sources(self, db: Session, *, instance, sources: list) -> list[IngestionResult]:
        results: list[IngestionResult] = []

        for source in sources:
            passage = db.scalar(
                select(HippoPassageNode).where(
                    HippoPassageNode.system_instance_id == instance.id,
                    HippoPassageNode.canonical_source_id == source.id,
                    HippoPassageNode.content_hash == source.content_hash,
                )
            )

            if passage is None:
                passage = HippoPassageNode(
                    system_instance_id=instance.id,
                    canonical_source_id=source.id,
                    passage_text=source.content_text,
                    embedding_id=None,
                    source_type=source.source_type,
                    content_hash=source.content_hash,
                    provider_node_id=None,
                    is_active=True,
                )
                db.add(passage)
                db.flush()
            else:
                passage.is_active = True

            entities = self.index_entities(db=db, instance=instance, passage=passage, source=source)
            self.index_fact_edges(db=db, instance=instance, passage=passage, entities=entities)

            results.append(
                IngestionResult(
                    native_record_type="hippo_passage_node",
                    native_record_id=passage.id,
                    canonical_source_id=source.id,
                    source_hash=source.content_hash,
                    status="indexed",
                )
            )

        db.add(
            HippoIndexRun(
                system_instance_id=instance.id,
                provider_version=None,
                openie_provider=create_hipporag_provider(settings).openie_status(),
                embedding_configuration={"provider": settings.memory_embedding_provider},
                ppr_configuration={"status": "available", "mode": "local_entity_propagation"},
                source_cutoff_time=instance.source_cutoff_time,
                status="completed",
            )
        )
        db.flush()

        return results

    def retrieve(self, db: Session, *, instance, query: str, top_k: int, token_budget: int, retrieval_mode):
        rows = list(
            db.execute(
                select(HippoPassageNode, CanonicalMemorySource)
                .join(CanonicalMemorySource, HippoPassageNode.canonical_source_id == CanonicalMemorySource.id)
                .where(
                    HippoPassageNode.system_instance_id == instance.id,
                    HippoPassageNode.is_active.is_(True),
                    CanonicalMemorySource.patient_id == instance.patient_id,
                    CanonicalMemorySource.is_active.is_(True),
                )
            ).all()
        )
        scored = []

        for passage, source in rows:
            entities = self.get_passage_entities(db=db, passage_id=passage.id)
            score, matched_entities = passage_score(
                query=query,
                passage=passage.passage_text,
                passage_entities=entities,
            )
            scored.append((score, matched_entities, entities, passage, source))

        ranked = sorted(scored, key=lambda item: item[0], reverse=True)
        items = [
            MemoryContextItem(
                rank=index + 1,
                score=score,
                source_type=source.source_type,
                source_subtype=source.source_subtype,
                content_preview=source_preview(passage.passage_text),
                content=passage.passage_text,
                canonical_source_id=source.id,
                system_native_type="hippo_passage_node",
                system_native_id=passage.id,
                document_id=source.document_id,
                page_number=source.page_number,
                section_id=source.section_id,
                conversation_id=source.conversation_id,
                message_id=source.message_id,
                event_time=source.event_time,
                token_count=max(1, (len(passage.passage_text or "") + 3) // 4),
                graph_score=score,
                metadata={
                    "matched_entities": matched_entities,
                    "passage_entities": entities[:12],
                    "retrieval_mode": retrieval_mode or "ppr",
                    "activation": "local_entity_propagation",
                },
            )
            for index, (score, matched_entities, entities, passage, source) in enumerate(ranked)
            if score > 0
        ]
        budget = apply_token_budget(items, token_budget=token_budget)

        return budget.included[:top_k], [], "ready"

    def get_statistics(self, db: Session, *, instance) -> dict:
        passages = db.scalar(
            select(func.count()).select_from(HippoPassageNode).where(
                HippoPassageNode.system_instance_id == instance.id,
                HippoPassageNode.is_active.is_(True),
            )
        )
        entity_nodes = db.scalar(
            select(func.count()).select_from(HippoEntityNode).where(HippoEntityNode.system_instance_id == instance.id)
        )
        fact_edges = db.scalar(
            select(func.count()).select_from(HippoFactEdge).where(HippoFactEdge.system_instance_id == instance.id)
        )

        return {
            "passages": int(passages or 0),
            "entity_nodes": int(entity_nodes or 0),
            "fact_edges": int(fact_edges or 0),
            "provider": create_hipporag_provider(settings).configuration()["provider"],
            "openie": create_hipporag_provider(settings).openie_status(),
        }

    def index_entities(self, db: Session, *, instance, passage: HippoPassageNode, source) -> list[HippoEntityNode]:
        indexed_entities = []

        for entity_data in extract_entities(source.content_text):
            entity = db.scalar(
                select(HippoEntityNode).where(
                    HippoEntityNode.system_instance_id == instance.id,
                    HippoEntityNode.normalized_name == entity_data["normalized_name"],
                )
            )

            if entity is None:
                entity = HippoEntityNode(
                    system_instance_id=instance.id,
                    entity_name=entity_data["name"],
                    normalized_name=entity_data["normalized_name"],
                    entity_type=entity_data["entity_type"],
                    embedding_id=None,
                    provider_node_id=None,
                )
                db.add(entity)
                db.flush()

            edge = db.scalar(
                select(HippoPassageEntityEdge).where(
                    HippoPassageEntityEdge.passage_node_id == passage.id,
                    HippoPassageEntityEdge.entity_node_id == entity.id,
                )
            )

            if edge is None:
                db.add(
                    HippoPassageEntityEdge(
                        passage_node_id=passage.id,
                        entity_node_id=entity.id,
                        edge_type="mentions",
                        weight=float(entity_data["frequency"]),
                    )
                )
            else:
                edge.weight = float(entity_data["frequency"])

            indexed_entities.append(entity)

        return indexed_entities

    def index_fact_edges(self, db: Session, *, instance, passage: HippoPassageNode, entities: list[HippoEntityNode]) -> None:
        for left_index, left in enumerate(entities):
            for right in entities[left_index + 1 :]:
                edge = db.scalar(
                    select(HippoFactEdge).where(
                        HippoFactEdge.system_instance_id == instance.id,
                        HippoFactEdge.subject_node_id == left.id,
                        HippoFactEdge.object_node_id == right.id,
                        HippoFactEdge.source_passage_id == passage.id,
                    )
                )

                if edge is None:
                    db.add(
                        HippoFactEdge(
                            system_instance_id=instance.id,
                            subject_node_id=left.id,
                            predicate="co_occurs_with",
                            object_node_id=right.id,
                            source_passage_id=passage.id,
                            edge_weight=1.0,
                            provider_edge_id=None,
                        )
                    )
                else:
                    edge.edge_weight = float(edge.edge_weight or 0) + 1.0

    def get_passage_entities(self, db: Session, *, passage_id) -> list[str]:
        rows = db.execute(
            select(HippoEntityNode.normalized_name)
            .join(HippoPassageEntityEdge, HippoPassageEntityEdge.entity_node_id == HippoEntityNode.id)
            .where(HippoPassageEntityEdge.passage_node_id == passage_id)
        ).all()

        return [row[0] for row in rows]
