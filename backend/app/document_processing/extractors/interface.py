from __future__ import annotations

from typing import Protocol

from app.document_processing.schemas import ExtractionResult


class DocumentTextExtractor(Protocol):
    extractor_name: str
    extractor_version: str

    def extract(self, content: bytes) -> ExtractionResult:
        ...
