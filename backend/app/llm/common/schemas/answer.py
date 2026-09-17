from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


UncertaintyLevel = Literal["low", "moderate", "high", "unknown"]


class GroundedCitation(BaseModel):
    citation_id: str
    canonical_source_id: Optional[UUID] = None
    document_id: Optional[UUID] = None
    page_number: Optional[int] = None
    section_id: Optional[UUID] = None
    source_type: Optional[str] = None
    claim_ids: list[str] = Field(default_factory=list)


class GeneratedAnswerClaim(BaseModel):
    claim_id: str
    claim_text: str = Field(min_length=1)
    subject: Optional[str] = None
    predicate: Optional[str] = None
    value: Optional[str] = None
    normalized_value: Optional[str] = None
    unit: Optional[str] = None
    status: Optional[str] = None
    negation: bool = False
    valid_time: Optional[datetime] = None
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    uncertainty: Optional[UncertaintyLevel] = None
    citation_ids: list[str] = Field(default_factory=list)


class GroundedAnswer(BaseModel):
    answer: str = Field(min_length=1)
    atomic_claims: list[GeneratedAnswerClaim] = Field(default_factory=list)
    citations: list[GroundedCitation] = Field(default_factory=list)
    insufficient_evidence: bool
    uncertainty: UncertaintyLevel
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    conflicts: list[str] = Field(default_factory=list)
    safety_note: Optional[str] = None
    follow_up_suggestions: list[str] = Field(default_factory=list)


class LlmContextBlock(BaseModel):
    citation_id: str
    source_type: Optional[str] = None
    event_time: Optional[datetime] = None
    canonical_source_id: Optional[UUID] = None
    document_id: Optional[UUID] = None
    page_number: Optional[int] = None
    section_id: Optional[UUID] = None
    confidence: Optional[float] = None
    content: str


class LlmProviderRequest(BaseModel):
    task_type: str
    system_prompt: str
    user_prompt: str
    message_history: list[dict] = Field(default_factory=list)
    context: list[LlmContextBlock] = Field(default_factory=list)
    model_configuration: dict = Field(default_factory=dict)
    trace_metadata: dict = Field(default_factory=dict)


class LlmProviderResult(BaseModel):
    content: str
    structured_value: Optional[BaseModel] = None
    provider: str
    model: str
    prompt_version: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    duration_ms: int
    finish_reason: Optional[str] = None
    request_identifier: Optional[str] = None
    retry_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ValidatedAnswerResult(BaseModel):
    answer: GroundedAnswer
    invalid_citation_ids: list[str] = Field(default_factory=list)


class LlmStatusResponse(BaseModel):
    provider: str
    status: str
    model: str
    fallback_model: Optional[str]
    fallback_allowed: bool
    experiment_mode: bool
    prompt_version: int
    data_egress_mode: str
    identifiable_data_allowed: bool
    api_key_configured: bool
    supports_streaming: bool
    supports_structured_output: bool
