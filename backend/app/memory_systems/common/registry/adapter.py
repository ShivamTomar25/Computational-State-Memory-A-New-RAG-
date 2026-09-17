from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.memory_systems.common.enums.status import SYSTEM_METADATA
from app.memory_systems.common.schemas.canonical import IngestionResult
from app.memory_systems.common.schemas.memory import CapabilityStatus, MemoryContextItem


class MemorySystemAdapter(ABC):
    system_type: str

    @property
    def metadata(self) -> dict:
        return SYSTEM_METADATA[self.system_type]

    @property
    def display_name(self) -> str:
        return self.metadata["display_name"]

    @property
    def supports_live_generation(self) -> bool:
        return False

    @property
    def supports_incremental_ingestion(self) -> bool:
        return True

    @property
    def requires_embeddings(self) -> bool:
        return bool(self.metadata["requires_embeddings"])

    @property
    def requires_llm(self) -> bool:
        return bool(self.metadata["requires_llm"])

    @property
    def requires_external_provider(self) -> bool:
        return bool(self.metadata["requires_external_provider"])

    def capability_status(self) -> CapabilityStatus:
        return CapabilityStatus(
            ingestion="available",
            retrieval="available",
            conversation_memory="available",
            answer_generation="requires_llm",
            incremental_update="available",
            embeddings="requires_embeddings" if self.requires_embeddings else "available",
            provider="available",
        )

    def configuration(self) -> dict:
        return {}

    def initialize(self, db: Session, *, instance) -> None:
        return None

    @abstractmethod
    def ingest_sources(self, db: Session, *, instance, sources: list) -> list[IngestionResult]:
        ...

    @abstractmethod
    def retrieve(
        self,
        db: Session,
        *,
        instance,
        query: str,
        top_k: int,
        token_budget: int,
        retrieval_mode: Optional[str],
    ) -> tuple[list[MemoryContextItem], list[str], str]:
        ...

    @abstractmethod
    def get_statistics(self, db: Session, *, instance) -> dict:
        ...

    def rebuild(self, db: Session, *, instance) -> None:
        return None

    def handle_conversation_message(self, db: Session, *, instance, conversation, message) -> None:
        return None


def source_preview(text: str, max_length: int = 300) -> str:
    cleaned = " ".join((text or "").split())

    if len(cleaned) <= max_length:
        return cleaned

    return f"{cleaned[:max_length].rstrip()}..."


def source_to_context_item(
    *,
    source,
    rank: int,
    score: Optional[float],
    native_type: Optional[str],
    native_id: Optional[UUID],
    include_content: bool = True,
    dense_rank: Optional[int] = None,
    lexical_rank: Optional[int] = None,
    graph_score: Optional[float] = None,
    metadata: Optional[dict] = None,
) -> MemoryContextItem:
    return MemoryContextItem(
        rank=rank,
        score=score,
        source_type=source.source_type,
        source_subtype=source.source_subtype,
        content_preview=source_preview(source.content_text),
        content=source.content_text if include_content else None,
        canonical_source_id=source.id,
        system_native_type=native_type,
        system_native_id=native_id,
        document_id=source.document_id,
        page_number=source.page_number,
        section_id=source.section_id,
        conversation_id=source.conversation_id,
        message_id=source.message_id,
        event_time=source.event_time,
        token_count=max(1, (len(source.content_text or "") + 3) // 4),
        dense_rank=dense_rank,
        lexical_rank=lexical_rank,
        graph_score=graph_score,
        metadata=metadata or {},
    )
