from __future__ import annotations

import re
from datetime import date
from typing import Optional

from app.document.enums import DOCUMENT_TYPES
from app.document.exceptions import InvalidDocumentDate, InvalidDocumentType


SHA256_PATTERN = re.compile(r"^[a-fA-F0-9]{64}$")


def normalize_document_type(value: Optional[str]) -> str:
    cleaned_value = clean_optional_string(value) or "other"
    normalized_value = cleaned_value.strip().lower().replace(" ", "_").replace("-", "_")

    if normalized_value not in DOCUMENT_TYPES:
        raise InvalidDocumentType("Document type is not supported.")

    return normalized_value


def normalize_title(value: Optional[str]) -> Optional[str]:
    return truncate_optional_string(value, 220)


def normalize_description(value: Optional[str]) -> Optional[str]:
    return truncate_optional_string(value, 5000)


def validate_document_date(value: Optional[date]) -> Optional[date]:
    if value is not None and value > date.today():
        raise InvalidDocumentDate("Document date cannot be in the future.")

    return value


def normalize_sha256(value: Optional[str]) -> Optional[str]:
    cleaned_value = clean_optional_string(value)

    if cleaned_value is None:
        return None

    if not SHA256_PATTERN.fullmatch(cleaned_value):
        raise ValueError("SHA-256 checksum is malformed.")

    return cleaned_value.lower()


def clean_optional_string(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None

    cleaned_value = str(value).strip()

    return cleaned_value or None


def truncate_optional_string(value: Optional[str], max_length: int) -> Optional[str]:
    cleaned_value = clean_optional_string(value)

    if cleaned_value is None:
        return None

    return cleaned_value[:max_length]
