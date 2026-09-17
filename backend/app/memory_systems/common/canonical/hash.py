from __future__ import annotations

import hashlib
import json


def stable_content_hash(*, content_text: str, structured_payload: dict) -> str:
    payload = {
        "content_text": content_text,
        "structured_payload": structured_payload,
    }
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()
