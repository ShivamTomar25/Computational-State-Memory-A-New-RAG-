from __future__ import annotations

import re


def normalize_text(value: str) -> str:
    text = value.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def count_words(value: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", value))


def is_probably_binary(content: bytes) -> bool:
    if not content:
        return False

    sample = content[:4096]

    if b"\x00" in sample:
        return True

    control_bytes = sum(
        1
        for byte in sample
        if byte < 32 and byte not in {9, 10, 12, 13}
    )

    return control_bytes / len(sample) > 0.3


def decode_text_content(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue

    return content.decode("utf-8", errors="replace")
