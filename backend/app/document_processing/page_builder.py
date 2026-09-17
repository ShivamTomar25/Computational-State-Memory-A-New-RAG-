from __future__ import annotations

from app.document_processing.detectors.pdf_text_quality import assess_text_quality
from app.document_processing.schemas import ExtractedPage


def build_page_rows(pages: list[ExtractedPage]) -> list[dict]:
    quality = assess_text_quality(pages)
    rows: list[dict] = []

    for page in pages:
        likely_requires_ocr = not page.has_text or (
            page.character_count < 20 and quality.status in {"low", "unusable"}
        )
        extraction_status = "extracted" if page.has_text else "no_text_found"

        rows.append(
            {
                "page_number": page.page_number,
                "raw_text": page.raw_text,
                "normalized_text": page.normalized_text,
                "character_count": page.character_count,
                "word_count": page.word_count,
                "text_quality_score": quality.score if page.has_text else 0,
                "has_text": page.has_text,
                "likely_requires_ocr": likely_requires_ocr,
                "extraction_status": extraction_status,
            }
        )

    return rows
