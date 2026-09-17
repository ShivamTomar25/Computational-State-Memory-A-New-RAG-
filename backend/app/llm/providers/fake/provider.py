from __future__ import annotations

import time

from pydantic import BaseModel

from app.config import settings
from app.llm.common.schemas.answer import GroundedAnswer, LlmProviderRequest, LlmProviderResult
from app.llm.common.token_budget.counter import estimate_llm_tokens


class DeterministicFakeChatProvider:
    supports_structured_output = True
    supports_streaming = False

    def invoke_structured(
        self,
        request: LlmProviderRequest,
        response_schema: type[BaseModel],
    ) -> LlmProviderResult:
        started = time.monotonic()
        first_citation = request.context[0].citation_id if request.context else "C0"
        answer = GroundedAnswer(
            answer="The available context was reviewed. Use the cited source for confirmation.",
            citations=[] if first_citation == "C0" else [{"citation_id": first_citation}],
            insufficient_evidence=not bool(request.context),
            uncertainty="moderate" if request.context else "high",
            conflicts=[],
            safety_note="This is a deterministic test response.",
            follow_up_suggestions=[],
        )
        content = answer.model_dump_json()

        return LlmProviderResult(
            content=content,
            structured_value=answer,
            provider="fake",
            model="deterministic-fake-chat",
            prompt_version=settings.llm_prompt_version,
            input_tokens=sum(estimate_llm_tokens(item.content) for item in request.context),
            output_tokens=estimate_llm_tokens(content),
            total_tokens=sum(estimate_llm_tokens(item.content) for item in request.context) + estimate_llm_tokens(content),
            duration_ms=int((time.monotonic() - started) * 1000),
            finish_reason="stop",
        )

    def health(self) -> str:
        return "healthy"

    def model_metadata(self) -> dict:
        return {
            "provider": "fake",
            "model": "deterministic-fake-chat",
            "configured": True,
        }

    def count_tokens(self, text: str) -> int:
        return estimate_llm_tokens(text)
