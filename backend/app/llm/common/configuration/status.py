from __future__ import annotations

import importlib.util

from app.config import settings
from app.llm.common.schemas.answer import LlmStatusResponse


def get_sanitized_llm_status() -> LlmStatusResponse:
    status = get_lightweight_provider_status()
    supports_streaming = settings.llm_provider == "groq"
    supports_structured_output = settings.llm_provider in {"fake", "groq"}

    return LlmStatusResponse(
        provider=settings.llm_provider,
        status=status,
        model=settings.groq_model,
        fallback_model=settings.groq_fallback_model,
        fallback_allowed=settings.groq_allow_fallback,
        experiment_mode=settings.llm_experiment_mode,
        prompt_version=settings.llm_prompt_version,
        data_egress_mode=settings.llm_external_data_mode,
        identifiable_data_allowed=settings.llm_allow_identifiable_clinical_data,
        api_key_configured=bool(settings.groq_api_key),
        supports_streaming=supports_streaming,
        supports_structured_output=supports_structured_output,
    )


def get_lightweight_provider_status() -> str:
    if settings.llm_provider == "fake":
        return "healthy"

    if settings.llm_provider != "groq":
        return "not_configured"

    if not settings.groq_api_key:
        return "not_configured"

    if importlib.util.find_spec("langchain_groq") is None:
        return "unavailable"

    return "configured"
