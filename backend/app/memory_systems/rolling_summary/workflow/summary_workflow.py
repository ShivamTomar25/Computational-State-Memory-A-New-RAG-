from __future__ import annotations

from sqlalchemy.orm import Session

from app.memory_systems.rolling_summary.summarizer.service import RollingSummaryService


def run_summary_update(db: Session, *, instance, sources: list) -> None:
    RollingSummaryService().update_summary(db, instance=instance, sources=sources)
