from __future__ import annotations

import hashlib
import json
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.evaluation.exports.repositories import export_repository


def create_inline_export(db: Session, *, experiment_id: UUID, export_type: str, content: dict) -> dict:
    checksum = content_checksum(content)
    export = export_repository.create_export(
        db,
        {
            "experiment_id": experiment_id,
            "export_type": export_type,
            "object_path": f"inline://evaluation/{experiment_id}/{export_type}/{checksum[:16]}",
            "checksum": checksum,
        },
    )
    db.commit()
    db.refresh(export)
    return serialize_export(export, content=content)


def list_experiment_exports(db: Session, *, experiment_id: UUID) -> list[dict]:
    return [serialize_export(export) for export in export_repository.list_exports(db, experiment_id)]


def serialize_export(export, content: Optional[dict] = None) -> dict:
    payload = {
        "id": str(export.id),
        "experiment_id": str(export.experiment_id),
        "export_type": export.export_type,
        "object_path": export.object_path,
        "checksum": export.checksum,
        "created_at": export.created_at.isoformat(),
    }

    if content is not None:
        payload["content"] = content

    return payload


def content_checksum(content: dict) -> str:
    payload = json.dumps(content, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
