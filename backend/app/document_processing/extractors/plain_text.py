from __future__ import annotations

from app.config import settings
from app.document.exceptions import TextExtractionFailed
from app.document_processing.normalizers.text import (
    count_words,
    decode_text_content,
    is_probably_binary,
    normalize_text,
)
from app.document_processing.schemas import ExtractedPage, ExtractionResult


class PlainTextExtractor:
    extractor_name = "plain_text_extractor"
    extractor_version = "1.0"

    def extract(self, content: bytes) -> ExtractionResult:
        if is_probably_binary(content):
            raise TextExtractionFailed("Text file appears to be binary.")

        raw_text = decode_text_content(content)
        normalized_text = normalize_text(raw_text)

        if len(normalized_text) > settings.document_max_extracted_characters:
            raise TextExtractionFailed("Extracted text exceeds the configured limit.")

        page = ExtractedPage(
            page_number=1,
            raw_text=raw_text,
            normalized_text=normalized_text,
            character_count=len(normalized_text),
            word_count=count_words(normalized_text),
            has_text=bool(normalized_text),
        )

        return ExtractionResult(
            extraction_method="digital_text",
            extractor_name=self.extractor_name,
            extractor_version=self.extractor_version,
            raw_text=raw_text,
            normalized_text=normalized_text,
            pages=[page],
            sections=[],
            metadata={"source": "text/plain"},
        )
