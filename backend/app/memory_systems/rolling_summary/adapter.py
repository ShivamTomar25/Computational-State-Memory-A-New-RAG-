from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.memory_systems.common.models.memory import CanonicalMemorySource
from app.memory_systems.common.registry.adapter import MemorySystemAdapter, source_to_context_item
from app.memory_systems.common.schemas.canonical import IngestionResult
from app.memory_systems.common.schemas.memory import CapabilityStatus
from app.memory_systems.common.token_budget.service import apply_token_budget, estimate_tokens
from app.memory_systems.rolling_summary.models import (
    RollingSummaryPendingInput,
    RollingSummaryRecentItem,
)
from app.memory_systems.rolling_summary.repository.snapshots import get_latest_snapshot
from app.memory_systems.rolling_summary.service.readiness import rolling_summary_provider_status
from app.memory_systems.rolling_summary.workflow.summary_workflow import run_summary_update


class RollingSummaryAdapter(MemorySystemAdapter):
    system_type = "rolling_summary"

    def capability_status(self) -> CapabilityStatus:
        provider_status = rolling_summary_provider_status()
        ready = provider_status == "available"

        return CapabilityStatus(
            ingestion="available" if ready else provider_status,
            retrieval="available" if ready else "not_ready",
            conversation_memory="available",
            answer_generation="requires_llm",
            incremental_update="available" if ready else provider_status,
            embeddings="available",
            provider=provider_status,
        )

    def configuration(self) -> dict:
        return {
            "recent_window_tokens": settings.rolling_summary_recent_window_tokens,
            "summarizer_provider": settings.llm_provider,
            "summarizer_model": settings.groq_model,
        }

    def ingest_sources(self, db: Session, *, instance, sources: list) -> list[IngestionResult]:
        results: list[IngestionResult] = []

        for source in sources:
            pending = db.scalar(
                select(RollingSummaryPendingInput).where(
                    RollingSummaryPendingInput.system_instance_id == instance.id,
                    RollingSummaryPendingInput.canonical_source_id == source.id,
                )
            )

            if pending is None:
                pending = RollingSummaryPendingInput(
                    system_instance_id=instance.id,
                    canonical_source_id=source.id,
                    status="requires_llm",
                )
                db.add(pending)

            recent = db.scalar(
                select(RollingSummaryRecentItem).where(
                    RollingSummaryRecentItem.system_instance_id == instance.id,
                    RollingSummaryRecentItem.canonical_source_id == source.id,
                )
            )

            if recent is None:
                recent = RollingSummaryRecentItem(
                    system_instance_id=instance.id,
                    canonical_source_id=source.id,
                    content_snapshot=source.content_text,
                    event_time=source.event_time,
                    token_count=estimate_tokens(source.content_text),
                    is_active=True,
                )
                db.add(recent)
            else:
                recent.content_snapshot = source.content_text
                recent.token_count = estimate_tokens(source.content_text)
                recent.is_active = True

            db.flush()
            results.append(
                IngestionResult(
                    native_record_type="rolling_summary_pending_input",
                    native_record_id=pending.id,
                    canonical_source_id=source.id,
                    source_hash=source.content_hash,
                    status="indexed",
                )
            )

        run_summary_update(db, instance=instance, sources=sources)

        return results

    def retrieve(self, db: Session, *, instance, query: str, top_k: int, token_budget: int, retrieval_mode):
        latest_snapshot = get_latest_snapshot(db, system_instance_id=instance.id)
        rows = list(
            db.execute(
                select(RollingSummaryRecentItem, CanonicalMemorySource)
                .join(CanonicalMemorySource, RollingSummaryRecentItem.canonical_source_id == CanonicalMemorySource.id)
                .where(
                    RollingSummaryRecentItem.system_instance_id == instance.id,
                    RollingSummaryRecentItem.is_active.is_(True),
                )
                .order_by(RollingSummaryRecentItem.event_time.desc())
            ).all()
        )
        items = []

        if latest_snapshot is not None:
            newest_source = rows[0][1] if rows else None

            if newest_source is not None:
                items.append(
                    source_to_context_item(
                        source=newest_source,
                        rank=1,
                        score=1.0,
                        native_type="rolling_summary_snapshot",
                        native_id=latest_snapshot.id,
                        metadata={
                            "summary_status": latest_snapshot.summary_status,
                            "version_number": latest_snapshot.version_number,
                            "covered_cutoff_time": latest_snapshot.covered_cutoff_time.isoformat()
                            if latest_snapshot.covered_cutoff_time
                            else None,
                            "summary_text": latest_snapshot.summary_text,
                        },
                    )
                )
                items[-1].content = latest_snapshot.summary_text
                items[-1].content_preview = latest_snapshot.summary_text[:300]

        recent_items = [
            source_to_context_item(
                source=source,
                rank=len(items) + index + 1,
                score=None,
                native_type="rolling_summary_recent_item",
                native_id=recent.id,
                metadata={"summary_status": latest_snapshot.summary_status if latest_snapshot else "missing"},
            )
            for index, (recent, source) in enumerate(rows)
        ]
        items.extend(recent_items)
        budget = apply_token_budget(items, token_budget=min(token_budget, settings.rolling_summary_recent_window_tokens))

        if latest_snapshot is None:
            return budget.included[:top_k], ["Rolling summary has not generated a snapshot yet."], "not_ready"

        return budget.included[:top_k], [], "ready"

    def get_statistics(self, db: Session, *, instance) -> dict:
        pending = db.scalar(
            select(func.count()).select_from(RollingSummaryPendingInput).where(
                RollingSummaryPendingInput.system_instance_id == instance.id
            )
        )
        recent = db.scalar(
            select(func.count()).select_from(RollingSummaryRecentItem).where(
                RollingSummaryRecentItem.system_instance_id == instance.id,
                RollingSummaryRecentItem.is_active.is_(True),
            )
        )
        latest_snapshot = get_latest_snapshot(db, system_instance_id=instance.id)

        return {
            "pending_inputs": int(pending or 0),
            "recent_items": int(recent or 0),
            "summary_status": latest_snapshot.summary_status if latest_snapshot else "missing",
            "summary_versions": latest_snapshot.version_number if latest_snapshot else 0,
        }
