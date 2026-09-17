from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.evaluation.exports.models import EvaluationExport


def create_export(db: Session, data: dict) -> EvaluationExport:
    export = EvaluationExport(**data)
    db.add(export)
    db.flush()
    return export


def list_exports(db: Session, experiment_id: UUID) -> list[EvaluationExport]:
    return list(
        db.scalars(
            select(EvaluationExport)
            .where(EvaluationExport.experiment_id == experiment_id)
            .order_by(EvaluationExport.created_at.desc())
        ).all()
    )
