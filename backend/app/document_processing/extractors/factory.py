from __future__ import annotations

from app.document.exceptions import UnsupportedDocumentFormat
from app.document_processing.extractors.docx import DocxTextExtractor
from app.document_processing.extractors.pdf_text import PdfTextExtractor
from app.document_processing.extractors.plain_text import PlainTextExtractor


def extract_text_by_family(*, family: str, content: bytes):
    if family == "pdf":
        return PdfTextExtractor().extract(content)

    if family == "docx":
        return DocxTextExtractor().extract(content)

    if family == "text":
        return PlainTextExtractor().extract(content)

    raise UnsupportedDocumentFormat("Document format is not supported for extraction.")
