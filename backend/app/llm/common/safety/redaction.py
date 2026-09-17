from __future__ import annotations

import re
from dataclasses import dataclass


SECRET_PATTERNS = (
    re.compile(r"gsk_[A-Za-z0-9_\\-]+"),
    re.compile(r"postgresql\\+psycopg://[^\\s]+"),
    re.compile(r"Bearer\\s+[A-Za-z0-9._\\-]+", re.IGNORECASE),
)


def redact_secrets(value: str) -> str:
    redacted = value or ""

    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)

    return redacted


@dataclass(frozen=True)
class DeidentificationResult:
    text: str
    replacements: dict[str, str]


def deidentify_text(text: str, *, patient_name: str = "", email: str = "", phone: str = "", address: str = "") -> DeidentificationResult:
    replacements = {}
    result = text or ""

    for label, value in (
        ("PATIENT_NAME", patient_name),
        ("PATIENT_EMAIL", email),
        ("PATIENT_PHONE", phone),
        ("PATIENT_ADDRESS", address),
    ):
        cleaned = (value or "").strip()

        if cleaned:
            token = f"[{label}]"
            result = result.replace(cleaned, token)
            replacements[label] = token

    result = re.sub(r"\\b[\\w.+-]+@[\\w.-]+\\.[A-Za-z]{2,}\\b", "[EMAIL]", result)
    result = re.sub(r"\\b(?:\\+?\\d[\\d\\s().-]{7,}\\d)\\b", redact_phone_like_value, result)

    return DeidentificationResult(text=result, replacements=replacements)


def redact_phone_like_value(match) -> str:
    value = match.group(0)

    if re.fullmatch(r"\\d{4}-\\d{2}-\\d{2}", value):
        return value

    digits = re.sub(r"\\D", "", value)

    if len(digits) < 10:
        return value

    return "[PHONE]"
