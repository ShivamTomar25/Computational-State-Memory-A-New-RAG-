from __future__ import annotations

from app.config import settings
from app.document_processing.normalizers.text import count_words
from app.document_processing.schemas import ExtractedPage, TextQualityResult


def assess_text_quality(pages: list[ExtractedPage]) -> TextQualityResult:
    page_count = len(pages)
    character_count = sum(page.character_count for page in pages)
    word_count = count_words("\n".join(page.normalized_text for page in pages))
    empty_page_count = sum(1 for page in pages if not page.has_text)
    empty_page_ratio = empty_page_count / page_count if page_count else 1
    average_characters_per_page = character_count / page_count if page_count else 0

    if character_count == 0:
        status = "unusable"
        score = 0
    elif (
        character_count < settings.document_text_min_total_characters
        or average_characters_per_page < settings.document_text_min_average_characters_per_page
        or empty_page_ratio >= settings.document_text_max_empty_page_ratio
    ):
        status = "low"
        score = 35
    elif average_characters_per_page >= 400 and empty_page_ratio <= 0.2:
        status = "good"
        score = 90
    else:
        status = "acceptable"
        score = 70

    return TextQualityResult(
        score=score,
        status=status,
        character_count=character_count,
        word_count=word_count,
        page_count=page_count,
        empty_page_count=empty_page_count,
        empty_page_ratio=empty_page_ratio,
        average_characters_per_page=average_characters_per_page,
    )
