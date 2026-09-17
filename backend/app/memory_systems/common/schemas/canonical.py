from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID


@dataclass(frozen=True)
class CanonicalSourceInput:
    patient_id: UUID
    source_type: str
    source_subtype: str
    source_record_id: str
    source_version: str
    content_text: str
    structured_payload: dict
    event_time: datetime
    valid_time: Optional[datetime]
    recorded_time: datetime
    document_id: Optional[UUID] = None
    page_number: Optional[int] = None
    section_id: Optional[UUID] = None
    encounter_id: Optional[UUID] = None
    conversation_id: Optional[UUID] = None
    message_id: Optional[UUID] = None
    role: Optional[str] = None
    owning_system_instance_id: Optional[UUID] = None
    visibility_scope: str = "patient_shared"
    content_hash: str = ""


@dataclass(frozen=True)
class IngestionResult:
    native_record_type: str
    native_record_id: Optional[UUID]
    canonical_source_id: UUID
    source_hash: str
    status: str


@dataclass(frozen=True)
class AdapterRetrievalResult:
    items: list
    warnings: list[str]
    readiness_status: str
    statistics: dict
