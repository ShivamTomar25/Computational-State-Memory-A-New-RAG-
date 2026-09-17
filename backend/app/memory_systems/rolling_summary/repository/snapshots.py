from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.memory_systems.rolling_summary.models import (
    RollingSummaryCoverage,
    RollingSummarySnapshot,
)


def get_latest_snapshot(db: Session, *, system_instance_id: UUID) -> RollingSummarySnapshot | None:
    statement = (
        select(RollingSummarySnapshot)
        .where(RollingSummarySnapshot.system_instance_id == system_instance_id)
        .order_by(RollingSummarySnapshot.version_number.desc())
        .limit(1)
    )

    return db.scalar(statement)


def next_version_number(db: Session, *, system_instance_id: UUID) -> int:
    value = db.scalar(
        select(func.max(RollingSummarySnapshot.version_number)).where(
            RollingSummarySnapshot.system_instance_id == system_instance_id
        )
    )

    return int(value or 0) + 1


def create_snapshot(db: Session, *, data: dict, source_ids: list[UUID]) -> RollingSummarySnapshot:
    snapshot = RollingSummarySnapshot(**data)
    db.add(snapshot)
    db.flush()

    for source_id in source_ids:
        db.add(
            RollingSummaryCoverage(
                snapshot_id=snapshot.id,
                canonical_source_id=source_id,
                covered_at=data["covered_cutoff_time"],
            )
        )

    db.flush()
    return snapshot
