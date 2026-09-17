from __future__ import annotations

from app.document_processing.schemas import ExtractedSection, ExtractionResult


def build_section_rows(extraction: ExtractionResult) -> list[dict]:
    sections = extraction.sections

    if not sections and extraction.normalized_text:
        sections = [
            ExtractedSection(
                section_index=1,
                heading="Full document",
                section_type="document",
                normalized_text=extraction.normalized_text,
                page_start=1,
                page_end=len(extraction.pages) or 1,
                confidence=60,
            )
        ]

    return [
        {
            "section_index": section.section_index,
            "heading": section.heading,
            "section_type": section.section_type,
            "normalized_text": section.normalized_text,
            "page_start": section.page_start,
            "page_end": section.page_end,
            "extraction_method": extraction.extraction_method,
            "confidence": section.confidence,
        }
        for section in sections
        if section.normalized_text
    ]
