from __future__ import annotations

import re
from collections import Counter


STOP_WORDS = {
    "about",
    "after",
    "again",
    "also",
    "available",
    "before",
    "being",
    "clinical",
    "context",
    "controlled",
    "current",
    "during",
    "follow",
    "from",
    "have",
    "known",
    "latest",
    "medical",
    "note",
    "patient",
    "percent",
    "record",
    "records",
    "should",
    "system",
    "test",
    "that",
    "their",
    "there",
    "this",
    "using",
    "what",
    "when",
    "where",
    "which",
    "with",
}


def extract_entities(text: str, *, limit: int = 20) -> list[dict]:
    tokens = [normalize_token(token) for token in re.findall(r"[A-Za-z][A-Za-z0-9.-]*", text or "")]
    tokens = [token for token in tokens if is_entity_token(token)]
    counts = Counter(tokens)

    return [
        {
            "name": display_name(token),
            "normalized_name": token,
            "entity_type": classify_entity(token),
            "frequency": frequency,
        }
        for token, frequency in counts.most_common(limit)
    ]


def lexical_score(query: str, text: str) -> float:
    query_terms = set(tokenize(query))

    if not query_terms:
        return 0

    text_terms = set(tokenize(text))

    return len(query_terms & text_terms) / len(query_terms)


def tokenize(text: str) -> list[str]:
    return [
        token
        for token in (normalize_token(value) for value in re.findall(r"[A-Za-z][A-Za-z0-9.-]*", text or ""))
        if token and token not in STOP_WORDS
    ]


def normalize_token(value: str) -> str:
    return value.strip(".,:;()[]{}").lower()


def is_entity_token(token: str) -> bool:
    if not token or token in STOP_WORDS:
        return False

    if any(character.isdigit() for character in token):
        return True

    return len(token) >= 4


def display_name(token: str) -> str:
    if any(character.isdigit() for character in token):
        return token.upper()

    return token.replace("-", " ").title()


def classify_entity(token: str) -> str:
    if any(marker in token for marker in ("a1c", "bp", "hba1c")):
        return "measurement"

    if token in {"amlodipine", "metformin", "insulin", "atorvastatin", "lisinopril"}:
        return "medication"

    if token in {"allergy", "hypertension", "diabetes", "asthma", "fever"}:
        return "condition"

    return "clinical_term"
