from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.storage.schemas import SignedUploadResult


class DocumentUploadInitiateRequest(BaseModel):
    original_filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=160)
    size_bytes: int = Field(gt=0)
    document_type: str = Field(default="other", max_length=50)
    title: Optional[str] = Field(default=None, max_length=220)
    description: Optional[str] = Field(default=None, max_length=5000)
    document_date: Optional[date] = None
    encounter_id: Optional[UUID] = None
    checksum_algorithm: Optional[str] = Field(default=None, max_length=20)
    checksum: Optional[str] = Field(default=None, max_length=128)
    replaces_document_id: Optional[UUID] = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("checksum_algorithm")
    @classmethod
    def normalize_checksum_algorithm(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None

        cleaned_value = value.strip().lower()

        if cleaned_value not in {"sha256"}:
            raise ValueError("Only SHA-256 checksums are supported.")

        return cleaned_value


class DocumentUploadInitiateResponse(BaseModel):
    document_id: UUID
    upload_status: str
    verification_status: str
    processing_status: str
    object_path: str
    upload: SignedUploadResult
    completion_endpoint: str
    upload_deadline_at: datetime


class DocumentUploadCompleteRequest(BaseModel):
    checksum: Optional[str] = Field(default=None, max_length=128)

    model_config = ConfigDict(extra="forbid")


class DocumentDirectUploadResponse(BaseModel):
    document: "DocumentDetailResponse"
    duplicate_warning: Optional[str] = None


class DocumentUpdate(BaseModel):
    document_type: Optional[str] = Field(default=None, max_length=50)
    title: Optional[str] = Field(default=None, max_length=220)
    description: Optional[str] = Field(default=None, max_length=5000)
    document_date: Optional[date] = None
    encounter_id: Optional[UUID] = None

    model_config = ConfigDict(extra="forbid")


class DocumentSummaryResponse(BaseModel):
    id: UUID
    patient_id: UUID
    encounter_id: Optional[UUID]
    document_type: str
    title: Optional[str]
    description: Optional[str]
    original_filename: str
    safe_filename: str
    file_extension: str
    declared_content_type: str
    detected_content_type: Optional[str]
    size_bytes_expected: int
    size_bytes_actual: Optional[int]
    document_date: Optional[date]
    source_type: str
    upload_status: str
    verification_status: str
    processing_status: str
    text_extraction_status: str
    ocr_requirement_status: str
    duplicate_of_document_id: Optional[UUID]
    failure_code: Optional[str]
    failure_reason: Optional[str]
    version_number: int
    is_current_version: bool
    is_active: bool
    uploaded_at: Optional[datetime]
    verified_at: Optional[datetime]
    processing_started_at: Optional[datetime]
    processing_completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentDetailResponse(DocumentSummaryResponse):
    page_count: int = 0
    section_count: int = 0
    artifact_count: int = 0
    extracted_text_available: bool = False
    replaces_document_id: Optional[UUID]
    superseded_by_document_id: Optional[UUID]


class DocumentListResponse(BaseModel):
    items: list[DocumentSummaryResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class SignedDocumentUrlResponse(BaseModel):
    document_id: UUID
    signed_url: str
    expires_in: int
    disposition: str


class DocumentProcessingRequest(BaseModel):
    force: bool = False

    model_config = ConfigDict(extra="forbid")


class DocumentProcessingJobResponse(BaseModel):
    id: UUID
    document_id: UUID
    patient_id: UUID
    job_type: str
    status: str
    attempt_number: int
    max_attempts: int
    queued_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    next_retry_at: Optional[datetime]
    failure_code: Optional[str]
    failure_reason: Optional[str]
    processor_name: str
    processor_version: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentProcessingStatusResponse(BaseModel):
    document: DocumentDetailResponse
    jobs: list[DocumentProcessingJobResponse]


class DocumentTextResponse(BaseModel):
    id: UUID
    document_id: UUID
    extraction_method: str
    extractor_name: str
    extractor_version: str
    normalized_text: Optional[str]
    character_count: int
    word_count: int
    page_count: int
    detected_language: Optional[str]
    quality_score: Optional[int]
    quality_status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentPageResponse(BaseModel):
    id: UUID
    document_id: UUID
    page_number: int
    normalized_text: str
    character_count: int
    word_count: int
    text_quality_score: Optional[int]
    has_text: bool
    likely_requires_ocr: bool
    extraction_status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentSectionResponse(BaseModel):
    id: UUID
    document_id: UUID
    section_index: int
    heading: Optional[str]
    section_type: Optional[str]
    normalized_text: str
    page_start: Optional[int]
    page_end: Optional[int]
    extraction_method: str
    confidence: Optional[int]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentArtifactResponse(BaseModel):
    id: UUID
    document_id: UUID
    artifact_type: str
    content_type: str
    size_bytes: Optional[int]
    checksum: Optional[str]
    processor_name: str
    processor_version: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentAuditEventResponse(BaseModel):
    id: UUID
    document_id: UUID
    patient_id: UUID
    doctor_id: Optional[UUID]
    action: str
    status: str
    actor_type: str
    request_id: Optional[str]
    metadata_json: dict
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentReconciliationIssue(BaseModel):
    document_id: UUID
    issue_type: str
    status: str
    detail: str


class DocumentReconciliationResponse(BaseModel):
    issues: list[DocumentReconciliationIssue]
    total: int


DocumentDirectUploadResponse.model_rebuild()
