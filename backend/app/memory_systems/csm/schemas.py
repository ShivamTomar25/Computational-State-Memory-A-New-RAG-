from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CsmEvidenceResponse(BaseModel):
    id: UUID
    state_id: Optional[UUID] = None
    review_id: Optional[UUID] = None
    canonical_source_id: UUID
    group: str
    source_title: str
    source_type: str
    effective_date: str
    excerpt: str
    evidence_status: str
    verification: str
    contribution: str
    document_id: Optional[UUID] = None
    page_number: Optional[int] = None
    section_id: Optional[UUID] = None
    conversation_id: Optional[UUID] = None
    message_id: Optional[UUID] = None


class CsmStateResponse(BaseModel):
    id: UUID
    name: str
    category: str
    display_value: str
    unit: str = ""
    status: str
    support_status: str
    state_version: int
    effective_from: str
    effective_until: str
    last_observed_at: str
    updated_at: str
    next_review_date: str
    trend: str
    uncertainty_summary: str
    source_count: int
    active_evidence_count: int
    conflicting_evidence_ids: list[UUID] = Field(default_factory=list)
    pending_evidence_count: int
    evidence_ids: list[UUID] = Field(default_factory=list)
    upstream_dependency_ids: list[UUID] = Field(default_factory=list)
    downstream_dependency_ids: list[UUID] = Field(default_factory=list)
    activated: bool = False
    stale: bool = False
    update_operator: str
    status_reason: str
    optimistic: bool = False
    review_id: Optional[UUID] = None


class CsmHistoryResponse(BaseModel):
    id: UUID
    state_id: UUID
    effective_at: str
    previous_value: str
    new_value: str
    reason: str
    state_version: int


class CsmLineageResponse(BaseModel):
    type: str
    identifier: str
    timestamp: str
    actor: str
    version: str
    summary: str


class CsmConflictResponse(BaseModel):
    id: UUID
    state_id: Optional[UUID]
    evidence_a_id: UUID
    evidence_b_id: UUID
    conflict_type: str
    status: str
    resolution: Optional[str]
    created_at: str


class CsmReviewResponse(BaseModel):
    id: UUID
    proposed_claim: str
    proposed_state_type: str
    proposed_value: dict
    support_status: str
    risk_level: str
    status: str
    created_at: str
    reviewed_at: Optional[str] = None
    review_note: Optional[str] = None


class CsmSummaryResponse(BaseModel):
    availability: str
    state_version: int
    sync_status: str
    last_state_update: str
    total_active_states: int
    contested_states: int
    pending_review_states: int
    evidence_count: int
    conflict_count: int
    review_count: int


class CsmOverviewResponse(BaseModel):
    summary: CsmSummaryResponse
    states: list[CsmStateResponse]
    evidence: list[CsmEvidenceResponse]
    history: list[CsmHistoryResponse]
    lineage: list[CsmLineageResponse]
    conflicts: list[CsmConflictResponse]
    reviews: list[CsmReviewResponse]


class CsmReviewDecisionRequest(BaseModel):
    note: Optional[str] = Field(default=None, max_length=2000)
