from __future__ import annotations

from fastapi import APIRouter

from app.llm.common.configuration.status import get_sanitized_llm_status
from app.llm.common.schemas.answer import LlmStatusResponse


router = APIRouter(tags=["LLM"])


@router.get("/api/llm/status", response_model=LlmStatusResponse)
def llm_status() -> LlmStatusResponse:
    return get_sanitized_llm_status()
