from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.evaluation.experiments.models.experiment import Experiment, ExperimentClaim, ExperimentOutput, ExperimentSystemRun, ExperimentTurn
from app.evaluation.judges.human_review.models import EvaluationAnnotation


def get_owned_claim(db: Session, *, claim_id: UUID, doctor_id: UUID) -> Optional[ExperimentClaim]:
    return db.scalar(
        select(ExperimentClaim)
        .join(ExperimentOutput, ExperimentClaim.output_id == ExperimentOutput.id)
        .join(ExperimentTurn, ExperimentOutput.turn_id == ExperimentTurn.id)
        .join(ExperimentSystemRun, ExperimentTurn.system_run_id == ExperimentSystemRun.id)
        .join(Experiment, ExperimentSystemRun.experiment_id == Experiment.id)
        .where(ExperimentClaim.id == claim_id, Experiment.requested_by_doctor_id == doctor_id)
    )


def create_annotation(db: Session, data: dict) -> EvaluationAnnotation:
    annotation = EvaluationAnnotation(**data)
    db.add(annotation)
    db.flush()
    return annotation
