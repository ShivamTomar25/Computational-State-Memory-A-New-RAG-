from __future__ import annotations

from app.config import settings
from app.llm.providers.fake.provider import DeterministicFakeChatProvider
from app.llm.providers.groq.provider import GroqChatProvider
from app.llm.providers.unavailable.provider import UnavailableChatProvider


def get_chat_provider():
    if settings.llm_provider == "fake":
        return DeterministicFakeChatProvider()

    if settings.llm_provider == "groq":
        return GroqChatProvider()

    return UnavailableChatProvider()
