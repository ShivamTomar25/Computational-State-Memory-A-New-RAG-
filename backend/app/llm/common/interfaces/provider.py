from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel

from app.llm.common.schemas.answer import LlmProviderRequest, LlmProviderResult


class ChatProvider(Protocol):
    supports_structured_output: bool
    supports_streaming: bool

    def invoke_structured(
        self,
        request: LlmProviderRequest,
        response_schema: type[BaseModel],
    ) -> LlmProviderResult:
        ...

    def health(self) -> str:
        ...

    def model_metadata(self) -> dict:
        ...

    def count_tokens(self, text: str) -> int:
        ...
