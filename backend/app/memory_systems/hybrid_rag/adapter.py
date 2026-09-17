from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.memory_systems.common.embeddings.providers import cosine_similarity, get_embedding_provider
from app.memory_systems.common.models.memory import CanonicalMemorySource
from app.memory_systems.common.registry.adapter import MemorySystemAdapter, source_preview
from app.memory_systems.common.retrieval.chunking import chunk_source_text
from app.memory_systems.common.schemas.canonical import IngestionResult
from app.memory_systems.common.schemas.memory import CapabilityStatus, MemoryContextItem
from app.memory_systems.common.token_budget.service import apply_token_budget
from app.memory_systems.hybrid_rag.models import HybridRagChunk


class HybridRagAdapter(MemorySystemAdapter):
    system_type = "hybrid_rag"

    def capability_status(self) -> CapabilityStatus:
        provider = get_embedding_provider()
        return CapabilityStatus(
            ingestion=provider.health(),
            retrieval=provider.health(),
            conversation_memory="available",
            answer_generation="requires_llm",
            incremental_update="available",
            embeddings=provider.health(),
            provider="available",
        )

    def configuration(self) -> dict:
        provider = get_embedding_provider()
        return {
            "dense_candidates": settings.hybrid_dense_candidates,
            "lexical_candidates": settings.hybrid_lexical_candidates,
            "final_top_k": settings.hybrid_final_top_k,
            "rrf_k": settings.hybrid_rrf_k,
            "text_search_language": settings.hybrid_text_search_language,
            "embedding_provider": provider.provider_name,
            "embedding_model": provider.model_name,
        }

    def ingest_sources(self, db: Session, *, instance, sources: list) -> list[IngestionResult]:
        provider = get_embedding_provider()
        results: list[IngestionResult] = []

        for source in sources:
            chunks = chunk_source_text(
                source,
                chunk_size_tokens=settings.dense_rag_chunk_size_tokens,
                overlap_tokens=settings.dense_rag_chunk_overlap_tokens,
            )
            vectors = provider.embed_documents([chunk["chunk_text"] for chunk in chunks])

            for chunk, vector in zip(chunks, vectors):
                existing = db.scalar(
                    select(HybridRagChunk).where(
                        HybridRagChunk.system_instance_id == instance.id,
                        HybridRagChunk.canonical_source_id == source.id,
                        HybridRagChunk.chunk_index == chunk["chunk_index"],
                        HybridRagChunk.content_hash == chunk["content_hash"],
                    )
                )

                if existing is None:
                    hybrid_chunk = HybridRagChunk(
                        system_instance_id=instance.id,
                        canonical_source_id=source.id,
                        lexical_document=chunk["chunk_text"],
                        language_config=settings.hybrid_text_search_language,
                        dense_status="embedded",
                        lexical_status="indexed",
                        embedding_model=provider.model_name,
                        embedding_revision=provider.model_revision,
                        embedding_vector=vector,
                        is_active=True,
                        **chunk,
                    )
                    db.add(hybrid_chunk)
                    db.flush()
                else:
                    hybrid_chunk = existing
                    hybrid_chunk.embedding_vector = vector
                    hybrid_chunk.lexical_document = chunk["chunk_text"]
                    hybrid_chunk.is_active = True

                results.append(
                    IngestionResult(
                        native_record_type="hybrid_rag_chunk",
                        native_record_id=hybrid_chunk.id,
                        canonical_source_id=source.id,
                        source_hash=source.content_hash,
                        status="indexed",
                    )
                )

        return results

    def retrieve(self, db: Session, *, instance, query: str, top_k: int, token_budget: int, retrieval_mode):
        provider = get_embedding_provider()
        query_vector = provider.embed_query(query)
        query_terms = tokenize(query)
        rows = list(
            db.execute(
                select(HybridRagChunk, CanonicalMemorySource)
                .join(CanonicalMemorySource, HybridRagChunk.canonical_source_id == CanonicalMemorySource.id)
                .where(
                    HybridRagChunk.system_instance_id == instance.id,
                    HybridRagChunk.is_active.is_(True),
                    CanonicalMemorySource.patient_id == instance.patient_id,
                    CanonicalMemorySource.is_active.is_(True),
                )
            ).all()
        )
        dense = sorted(
            (
                (cosine_similarity(query_vector, chunk.embedding_vector), chunk, source)
                for chunk, source in rows
            ),
            key=lambda item: item[0],
            reverse=True,
        )[: settings.hybrid_dense_candidates]
        lexical = sorted(
            (
                (lexical_score(query_terms, chunk.lexical_document), chunk, source)
                for chunk, source in rows
            ),
            key=lambda item: item[0],
            reverse=True,
        )[: settings.hybrid_lexical_candidates]
        fused = {}

        for rank, (score, chunk, source) in enumerate(dense, start=1):
            fused.setdefault(chunk.id, {"chunk": chunk, "source": source, "dense_rank": rank, "lexical_rank": None, "dense_score": score, "lexical_score": None, "score": 0})
            fused[chunk.id]["score"] += 1 / (settings.hybrid_rrf_k + rank)

        for rank, (score, chunk, source) in enumerate(lexical, start=1):
            if score <= 0:
                continue
            fused.setdefault(chunk.id, {"chunk": chunk, "source": source, "dense_rank": None, "lexical_rank": rank, "dense_score": None, "lexical_score": score, "score": 0})
            fused[chunk.id]["lexical_rank"] = rank
            fused[chunk.id]["lexical_score"] = score
            fused[chunk.id]["score"] += 1 / (settings.hybrid_rrf_k + rank)

        ranked = sorted(fused.values(), key=lambda item: item["score"], reverse=True)
        items = [
            MemoryContextItem(
                rank=index + 1,
                score=item["score"],
                source_type=item["source"].source_type,
                source_subtype=item["source"].source_subtype,
                content_preview=source_preview(item["chunk"].chunk_text),
                content=item["chunk"].chunk_text,
                canonical_source_id=item["source"].id,
                system_native_type="hybrid_rag_chunk",
                system_native_id=item["chunk"].id,
                document_id=item["chunk"].document_id,
                page_number=item["chunk"].page_number,
                section_id=item["chunk"].section_id,
                conversation_id=item["chunk"].conversation_id,
                message_id=item["chunk"].message_id,
                event_time=item["chunk"].event_time,
                token_count=item["chunk"].token_count,
                dense_rank=item["dense_rank"],
                lexical_rank=item["lexical_rank"],
                metadata={
                    "dense_score": item["dense_score"],
                    "lexical_score": item["lexical_score"],
                    "fusion": "reciprocal_rank_fusion",
                },
            )
            for index, item in enumerate(ranked)
        ]
        budget = apply_token_budget(items, token_budget=token_budget)

        return budget.included[: min(top_k, settings.hybrid_final_top_k)], [], "ready"

    def get_statistics(self, db: Session, *, instance) -> dict:
        chunks = db.scalar(
            select(func.count()).select_from(HybridRagChunk).where(
                HybridRagChunk.system_instance_id == instance.id,
                HybridRagChunk.is_active.is_(True),
            )
        )

        return {
            "chunks": int(chunks or 0),
            "dense_status": get_embedding_provider().health(),
            "lexical_status": "available",
            "fusion": "reciprocal_rank_fusion",
        }


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9]+", text.lower()))


def lexical_score(query_terms: set[str], text: str) -> float:
    if not query_terms:
        return 0.0

    text_terms = tokenize(text)
    matches = len(query_terms & text_terms)

    return matches / len(query_terms)
