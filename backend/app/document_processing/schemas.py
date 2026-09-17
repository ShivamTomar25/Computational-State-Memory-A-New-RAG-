from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class FileSignatureResult:
    content_type: str
    extension: str
    family: str


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    raw_text: str
    normalized_text: str
    character_count: int
    word_count: int
    has_text: bool


@dataclass(frozen=True)
class ExtractedSection:
    section_index: int
    heading: Optional[str]
    section_type: Optional[str]
    normalized_text: str
    page_start: Optional[int]
    page_end: Optional[int]
    confidence: Optional[int] = None


@dataclass(frozen=True)
class ExtractionResult:
    extraction_method: str
    extractor_name: str
    extractor_version: str
    raw_text: str
    normalized_text: str
    pages: list[ExtractedPage]
    sections: list[ExtractedSection] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class TextQualityResult:
    score: int
    status: str
    character_count: int
    word_count: int
    page_count: int
    empty_page_count: int
    empty_page_ratio: float
    average_characters_per_page: float


@dataclass(frozen=True)
class OcrRequirementResult:
    status: str
    reason: str
