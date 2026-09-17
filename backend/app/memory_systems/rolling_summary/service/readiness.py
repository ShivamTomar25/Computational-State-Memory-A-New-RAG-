from __future__ import annotations

import importlib.util

from app.config import settings


def rolling_summary_provider_status() -> str:
    if settings.llm_provider == "fake":
        return "available"

    if settings.llm_provider != "groq":
        return "provider_not_configured"

    if not settings.groq_api_key:
        return "provider_not_configured"

    if importlib.util.find_spec("langchain_groq") is None:
        return "provider_not_installed"

    return "available"
