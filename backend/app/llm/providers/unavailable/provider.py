from __future__ import annotations

from pydantic import BaseModel

from app.config import settings
from app.llm.common.exceptions.errors import LlmNotConfigured
from app.llm.common.schemas.answer import LlmProviderRequest, LlmProviderResult
from app.llm.common.token_budget.counter import estimate_llm_tokens


class UnavailableChatProvider:
    supports_structured_output = False
    supports_streaming = False

    def invoke_structured(
        self,
        request: LlmProviderRequest,
        response_schema: type[BaseModel],
    ) -> LlmProviderResult:
        raise LlmNotConfigured("LLM provider is not configured.")

    def health(self) -> str:
        return "not_configured"

    def model_metadata(self) -> dict:
        return {
            "provider": settings.llm_provider,
            "model": settings.groq_model,
            "configured": False,
        }

    def count_tokens(self, text: str) -> int:
        return estimate_llm_tokens(text)
