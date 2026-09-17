from __future__ import annotations

from app.llm.common.schemas.answer import LlmProviderRequest, LlmProviderResult
from app.llm.providers.factory import get_chat_provider
from app.memory_systems.rolling_summary.schemas.summary import RollingSummaryDocument


class RollingSummaryGroqProvider:
    def status(self) -> str:
        provider = get_chat_provider()
        health = provider.health()

        if health == "configured":
            return "available"

        if health in {"disabled", "not_configured"}:
            return "provider_not_configured"

        return "provider_not_installed"

    def summarize(self, request: LlmProviderRequest) -> LlmProviderResult:
        provider = get_chat_provider()
        return provider.invoke_structured(request, RollingSummaryDocument)
