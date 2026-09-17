from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.config import settings
from app.document.exceptions import (
    MalformedDocument,
    PasswordProtectedPdf,
    TextExtractionFailed,
)
from app.document_processing.normalizers.text import count_words, normalize_text
from app.document_processing.schemas import ExtractedPage, ExtractionResult


class PdfTextExtractor:
    extractor_name = "pypdf_text_extractor"
    extractor_version = "1.0"

    def extract(self, content: bytes) -> ExtractionResult:
        try:
            reader = PdfReader(BytesIO(content))
        except PdfReadError as error:
            raise MalformedDocument("PDF file is malformed.") from error

        if reader.is_encrypted:
            raise PasswordProtectedPdf("Password-protected PDF files are not supported.")

        page_count = len(reader.pages)

        if page_count > settings.document_max_pdf_pages:
            raise TextExtractionFailed("PDF contains too many pages.")

        pages: list[ExtractedPage] = []

        for index, page in enumerate(reader.pages, start=1):
            try:
                raw_page_text = page.extract_text() or ""
            except Exception as error:
                raise TextExtractionFailed("Could not extract text from PDF page.") from error

            normalized_page_text = normalize_text(raw_page_text)
            pages.append(
                ExtractedPage(
                    page_number=index,
                    raw_text=raw_page_text,
                    normalized_text=normalized_page_text,
                    character_count=len(normalized_page_text),
                    word_count=count_words(normalized_page_text),
                    has_text=bool(normalized_page_text),
                )
            )

        raw_text = "\n\n".join(page.raw_text for page in pages)
        normalized_text = normalize_text("\n\n".join(page.normalized_text for page in pages))

        if len(normalized_text) > settings.document_max_extracted_characters:
            raise TextExtractionFailed("Extracted text exceeds the configured limit.")

        return ExtractionResult(
            extraction_method="pdf_text",
            extractor_name=self.extractor_name,
            extractor_version=self.extractor_version,
            raw_text=raw_text,
            normalized_text=normalized_text,
            pages=pages,
            sections=[],
            metadata={
                "page_count": page_count,
                "source": "application/pdf",
            },
        )
