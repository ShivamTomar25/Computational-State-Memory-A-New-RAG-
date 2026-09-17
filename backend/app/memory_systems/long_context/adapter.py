from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.memory_systems.common.models.memory import CanonicalMemorySource
from app.memory_systems.common.registry.adapter import MemorySystemAdapter, source_to_context_item
from app.memory_systems.common.schemas.canonical import IngestionResult
from app.memory_systems.common.schemas.memory import CapabilityStatus
from app.memory_systems.common.token_budget.service import apply_token_budget, estimate_tokens
from app.memory_systems.long_context.models import LongContextEntry, LongContextSnapshot


class LongContextAdapter(MemorySystemAdapter):
    system_type = "long_context"

    def capability_status(self) -> CapabilityStatus:
        return CapabilityStatus(
            ingestion="available",
            retrieval="available",
            conversation_memory="available",
            answer_generation="requires_llm",
            incremental_update="available",
            embeddings="available",
            provider="available",
        )

    def configuration(self) -> dict:
        return {
            "max_tokens": settings.long_context_max_tokens,
            "ordering": ["source_priority", "event_time", "canonical_source_id"],
        }

    def ingest_sources(self, db: Session, *, instance, sources: list) -> list[IngestionResult]:
        results: list[IngestionResult] = []
        active_hashes = []

        for index, source in enumerate(sources):
            active_hashes.append(source.content_hash)
            existing = db.scalar(
                select(LongContextEntry).where(
                    LongContextEntry.system_instance_id == instance.id,
                    LongContextEntry.canonical_source_id == source.id,
                    LongContextEntry.content_hash == source.content_hash,
                )
            )

            if existing is None:
                entry = LongContextEntry(
                    system_instance_id=instance.id,
                    canonical_source_id=source.id,
                    source_type=source.source_type,
                    content_snapshot=source.content_text,
                    structured_snapshot=source.structured_payload,
                    event_time=source.event_time,
                    source_priority=source_priority(source.source_type),
                    sequence_order=index,
                    token_count=estimate_tokens(source.content_text),
                    content_hash=source.content_hash,
                    is_active=True,
                )
                db.add(entry)
                db.flush()
            else:
                entry = existing
                entry.is_active = True

            results.append(
                IngestionResult(
                    native_record_type="long_context_entry",
                    native_record_id=entry.id,
                    canonical_source_id=source.id,
                    source_hash=source.content_hash,
                    status="indexed",
                )
            )

        source_hash = hashlib.sha256("".join(sorted(active_hashes)).encode("utf-8")).hexdigest()
        db.add(
            LongContextSnapshot(
                system_instance_id=instance.id,
                cutoff_time=instance.source_cutoff_time or datetime.now(timezone.utc),
                source_count=len(sources),
                token_count=sum(estimate_tokens(source.content_text) for source in sources),
                source_hash=source_hash,
            )
        )
        db.flush()

        return results

    def retrieve(self, db: Session, *, instance, query: str, top_k: int, token_budget: int, retrieval_mode):
        rows = list(
            db.execute(
                select(LongContextEntry, CanonicalMemorySource)
                .join(CanonicalMemorySource, LongContextEntry.canonical_source_id == CanonicalMemorySource.id)
                .where(
                    LongContextEntry.system_instance_id == instance.id,
                    LongContextEntry.is_active.is_(True),
                    CanonicalMemorySource.is_active.is_(True),
                )
                .order_by(
                    LongContextEntry.source_priority.asc(),
                    LongContextEntry.event_time.asc(),
                    LongContextEntry.canonical_source_id.asc(),
                )
            ).all()
        )
        items = [
            source_to_context_item(
                source=source,
                rank=index + 1,
                score=None,
                native_type="long_context_entry",
                native_id=entry.id,
                metadata={"policy": "deterministic_ordered_context"},
            )
            for index, (entry, source) in enumerate(rows)
        ]
        budget = apply_token_budget(items, token_budget=token_budget)

        for index, item in enumerate(budget.included, start=1):
            item.rank = index

        warnings = []

        if budget.excluded_count:
            warnings.append("Context exceeded the token budget; lower-ranked sources were excluded without summarization.")

        return budget.included[:top_k], warnings, "ready"

    def get_statistics(self, db: Session, *, instance) -> dict:
        entry_count = db.scalar(
            select(func.count()).select_from(LongContextEntry).where(
                LongContextEntry.system_instance_id == instance.id,
                LongContextEntry.is_active.is_(True),
            )
        )
        token_count = db.scalar(
            select(func.coalesce(func.sum(LongContextEntry.token_count), 0)).where(
                LongContextEntry.system_instance_id == instance.id,
                LongContextEntry.is_active.is_(True),
            )
        )

        return {
            "entries": int(entry_count or 0),
            "tokens": int(token_count or 0),
        }


def source_priority(source_type: str) -> int:
    priorities = {
        "patient_information": 1,
        "document": 2,
        "conversation": 3,
    }

    return priorities.get(source_type, 9)
