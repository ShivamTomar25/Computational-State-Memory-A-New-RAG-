from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.llm.common.models.llm import LlmCall


def create_llm_call(db: Session, *, data: dict) -> LlmCall:
    call = LlmCall(**data)
    db.add(call)
    db.flush()

    return call


def complete_llm_call(db: Session, *, call: LlmCall, data: dict) -> LlmCall:
    for field, value in data.items():
        setattr(call, field, value)

    call.completed_at = datetime.now(timezone.utc)
    db.flush()

    return call
