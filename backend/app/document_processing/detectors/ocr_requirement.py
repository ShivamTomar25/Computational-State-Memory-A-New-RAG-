from __future__ import annotations

from app.config import settings
from app.document_processing.schemas import OcrRequirementResult, TextQualityResult


def classify_ocr_requirement(quality: TextQualityResult) -> OcrRequirementResult:
    if quality.character_count == 0:
        return OcrRequirementResult(
            status="required",
            reason="No machine-readable text was extracted.",
        )

    if quality.empty_page_ratio >= settings.document_text_max_empty_page_ratio:
        return OcrRequirementResult(
            status="required",
            reason="Most pages do not contain machine-readable text.",
        )

    if quality.empty_page_count > 0 and quality.status in {"low", "acceptable"}:
        return OcrRequirementResult(
            status="mixed_document",
            reason="Some pages may require OCR.",
        )

    if quality.status == "low":
        return OcrRequirementResult(
            status="likely_required",
            reason="Extracted text quality is low.",
        )

    return OcrRequirementResult(
        status="not_required",
        reason="Machine-readable text is available.",
    )
