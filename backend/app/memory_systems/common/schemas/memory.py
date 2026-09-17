from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.llm.common.schemas.answer import GroundedAnswer


class CapabilityStatus(BaseModel):
    ingestion: str
    retrieval: str
    conversation_memory: str
    answer_generation: str
    incremental_update: str
    embeddings: str
    provider: str


class MemorySystemRegistryItem(BaseModel):
    system_type: str
    display_name: str
    description: str
    input_categories: list[str]
    storage_summary: str
    requires_embeddings: bool
    requires_llm: bool
    requires_external_provider: bool
    supports_incremental_ingestion: bool
    supports_conversation: bool
    supports_retrieval: bool
    supported_retrieval_modes: list[str]
    capability_status: CapabilityStatus


class MemorySystemInstanceResponse(BaseModel):
    id: Optional[UUID] = None
    patient_id: UUID
    system_type: str
    display_name: str
    status: str
    capability_status: CapabilityStatus
    configuration: dict
    pipeline_version: int
    initialized_at: Optional[datetime] = None
    last_synced_at: Optional[datetime] = None
    source_cutoff_time: Optional[datetime] = None
    failure_code: Optional[str] = None
    failure_reason: Optional[str] = None
    statistics: dict = Field(default_factory=dict)


class MemoryInitializeResponse(BaseModel):
    instance: MemorySystemInstanceResponse


class MemorySyncRequest(BaseModel):
    cutoff_time: Optional[datetime] = None
    mode: str = "incremental"
    include_patient_information: bool = True
    include_documents: bool = True
    include_conversation: bool = True

    model_config = ConfigDict(extra="forbid")


class MemoryRebuildRequest(BaseModel):
    confirm_rebuild: bool
    cutoff_time: Optional[datetime] = None
    include_patient_information: bool = True
    include_documents: bool = True
    include_conversation: bool = True

    model_config = ConfigDict(extra="forbid")


class MemoryIngestionRunResponse(BaseModel):
    id: UUID
    system_instance_id: UUID
    patient_id: UUID
    mode: str
    status: str
    cutoff_time: datetime
    pipeline_version: int
    configuration_snapshot: dict
    source_count: int
    processed_count: int
    skipped_count: int
    failed_count: int
    queued_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    failure_code: Optional[str]
    failure_reason: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MemoryIngestionRunDetailResponse(MemoryIngestionRunResponse):
    items: list[dict] = Field(default_factory=list)


class MemoryRetrieveRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: Optional[int] = Field(default=None, ge=1)
    token_budget: Optional[int] = Field(default=None, ge=1)
    retrieval_mode: Optional[str] = None
    conversation_id: Optional[UUID] = None
    include_content: bool = True
    include_citations: bool = True

    model_config = ConfigDict(extra="forbid")


class MemoryContextItem(BaseModel):
    rank: int
    score: Optional[float] = None
    source_type: Optional[str] = None
    source_subtype: Optional[str] = None
    content_preview: str
    content: Optional[str] = None
    canonical_source_id: Optional[UUID] = None
    system_native_type: Optional[str] = None
    system_native_id: Optional[UUID] = None
    document_id: Optional[UUID] = None
    page_number: Optional[int] = None
    section_id: Optional[UUID] = None
    conversation_id: Optional[UUID] = None
    message_id: Optional[UUID] = None
    event_time: Optional[datetime] = None
    token_count: int
    dense_rank: Optional[int] = None
    lexical_rank: Optional[int] = None
    graph_score: Optional[float] = None
    metadata: dict = Field(default_factory=dict)


class MemoryRetrieveResponse(BaseModel):
    system_type: str
    retrieval_run_id: Optional[UUID]
    readiness_status: str
    query: str
    context_items: list[MemoryContextItem]
    citations: list[dict] = Field(default_factory=list)
    token_count: int
    excluded_result_count: int
    warnings: list[str] = Field(default_factory=list)
    generation_status: str = "not_configured"


class MemoryStatisticsResponse(BaseModel):
    system_type: str
    status: str
    source_counts: dict
    storage: dict
    capability_status: CapabilityStatus


class MemoryConversationCreate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=220)

    model_config = ConfigDict(extra="forbid")


class MemoryConversationResponse(BaseModel):
    id: UUID
    patient_id: UUID
    doctor_id: UUID
    system_instance_id: UUID
    system_type: str
    title: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    last_message_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class MemoryMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=8000)

    model_config = ConfigDict(extra="forbid")


class MemoryMessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    patient_id: UUID
    system_instance_id: UUID
    role: str
    content: str
    sequence_number: int
    event_time: datetime
    token_count: Optional[int]
    generation_status: str
    retrieval_run_id: Optional[UUID]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MemoryMessagePostResponse(BaseModel):
    message: MemoryMessageResponse
    retrieval: MemoryRetrieveResponse
    generation_status: str
    assistant_message: Optional[MemoryMessageResponse] = None
    answer: Optional[GroundedAnswer] = None
    llm_call_id: Optional[UUID] = None
    model: Optional[str] = None
    prompt_version: Optional[int] = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    latency_ms: int = 0
    warnings: list[str] = Field(default_factory=list)
