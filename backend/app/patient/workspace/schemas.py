from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.patient.schemas import PatientResponse


class PatientWorkspaceInformationCounts(BaseModel):
    encounters: int = 0
    conditions: int = 0
    medications: int = 0
    allergies: int = 0
    measurements: int = 0
    notes: int = 0


class PatientWorkspaceDocumentCounts(BaseModel):
    total: int = 0
    pending_upload: int = 0
    uploaded: int = 0
    queued: int = 0
    processing: int = 0
    completed: int = 0
    failed: int = 0
    requires_ocr: int = 0


class PatientWorkspaceMemorySystemSummary(BaseModel):
    id: Optional[UUID] = None
    system_type: str
    display_name: str
    status: str
    initialized_at: Optional[datetime] = None
    last_synced_at: Optional[datetime] = None
    source_cutoff_time: Optional[datetime] = None
    failure_code: Optional[str] = None
    failure_reason: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PatientWorkspaceConversationSummary(BaseModel):
    id: UUID
    system_type: str
    title: Optional[str]
    status: str
    updated_at: datetime
    last_message_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class PatientWorkspaceSummaryResponse(BaseModel):
    patient: PatientResponse
    information_counts: PatientWorkspaceInformationCounts
    document_counts: PatientWorkspaceDocumentCounts
    memory_systems: list[PatientWorkspaceMemorySystemSummary]
    recent_conversations: list[PatientWorkspaceConversationSummary]
