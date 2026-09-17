from __future__ import annotations

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
from app.memory_systems.dense_rag.models import DenseRagChunk


class DenseRagAdapter(MemorySystemAdapter):
    system_type = "dense_rag"

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
            "chunk_size_tokens": settings.dense_rag_chunk_size_tokens,
            "chunk_overlap_tokens": settings.dense_rag_chunk_overlap_tokens,
            "top_k": settings.dense_rag_top_k,
            "embedding_provider": provider.provider_name,
            "embedding_model": provider.model_name,
            "embedding_dimension": provider.dimension,
            "vector_storage": "postgres_jsonb_embedding_vectors",
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
                    select(DenseRagChunk).where(
                        DenseRagChunk.system_instance_id == instance.id,
                        DenseRagChunk.canonical_source_id == source.id,
                        DenseRagChunk.chunk_index == chunk["chunk_index"],
                        DenseRagChunk.content_hash == chunk["content_hash"],
                    )
                )

                if existing is None:
                    dense_chunk = DenseRagChunk(
                        system_instance_id=instance.id,
                        canonical_source_id=source.id,
                        embedding_status="embedded",
                        embedding_model=provider.model_name,
                        embedding_revision=provider.model_revision,
                        embedding_vector=vector,
                        vector_record_id=None,
                        is_active=True,
                        **chunk,
                    )
                    db.add(dense_chunk)
                    db.flush()
                else:
                    dense_chunk = existing
                    dense_chunk.embedding_vector = vector
                    dense_chunk.is_active = True

                results.append(
                    IngestionResult(
                        native_record_type="dense_rag_chunk",
                        native_record_id=dense_chunk.id,
                        canonical_source_id=source.id,
                        source_hash=source.content_hash,
                        status="indexed",
                    )
                )

        return results

    def retrieve(self, db: Session, *, instance, query: str, top_k: int, token_budget: int, retrieval_mode):
        provider = get_embedding_provider()
        query_vector = provider.embed_query(query)
        rows = list(
            db.execute(
                select(DenseRagChunk, CanonicalMemorySource)
                .join(CanonicalMemorySource, DenseRagChunk.canonical_source_id == CanonicalMemorySource.id)
                .where(
                    DenseRagChunk.system_instance_id == instance.id,
                    DenseRagChunk.is_active.is_(True),
                    CanonicalMemorySource.patient_id == instance.patient_id,
                    CanonicalMemorySource.is_active.is_(True),
                )
            ).all()
        )
        scored = sorted(
            (
                (cosine_similarity(query_vector, chunk.embedding_vector), chunk, source)
                for chunk, source in rows
            ),
            key=lambda item: item[0],
            reverse=True,
        )
        items = [
            MemoryContextItem(
                rank=index + 1,
                score=score,
                source_type=source.source_type,
                source_subtype=source.source_subtype,
                content_preview=source_preview(chunk.chunk_text),
                content=chunk.chunk_text,
                canonical_source_id=source.id,
                system_native_type="dense_rag_chunk",
                system_native_id=chunk.id,
                document_id=chunk.document_id,
                page_number=chunk.page_number,
                section_id=chunk.section_id,
                conversation_id=chunk.conversation_id,
                message_id=chunk.message_id,
                event_time=chunk.event_time,
                token_count=chunk.token_count,
                dense_rank=index + 1,
                metadata={
                    "embedding_model": chunk.embedding_model,
                    "embedding_status": chunk.embedding_status,
                },
            )
            for index, (score, chunk, source) in enumerate(scored)
        ]
        budget = apply_token_budget(items, token_budget=token_budget)

        return budget.included[:top_k], [], "ready"

    def get_statistics(self, db: Session, *, instance) -> dict:
        chunks = db.scalar(
            select(func.count()).select_from(DenseRagChunk).where(
                DenseRagChunk.system_instance_id == instance.id,
                DenseRagChunk.is_active.is_(True),
            )
        )
        embedded = db.scalar(
            select(func.count()).select_from(DenseRagChunk).where(
                DenseRagChunk.system_instance_id == instance.id,
                DenseRagChunk.is_active.is_(True),
                DenseRagChunk.embedding_status == "embedded",
            )
        )

        return {
            "chunks": int(chunks or 0),
            "embedded_chunks": int(embedded or 0),
            "embedding_model": get_embedding_provider().model_name,
        }
