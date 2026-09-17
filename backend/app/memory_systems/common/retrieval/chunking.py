from __future__ import annotations

from app.config import settings
from app.memory_systems.common.canonical.hash import stable_content_hash
from app.memory_systems.common.token_budget.service import estimate_tokens


def chunk_source_text(source, *, chunk_size_tokens: int, overlap_tokens: int) -> list[dict]:
    text = source.content_text or ""

    if source.source_type in {"patient_information", "conversation"}:
        return [
            build_chunk(
                source=source,
                chunk_text=text,
                chunk_index=0,
            )
        ]

    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=max(200, chunk_size_tokens * 4),
            chunk_overlap=max(0, overlap_tokens * 4),
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        chunks = splitter.split_text(text)
    except Exception:
        chunks = fallback_chunks(text, chunk_size_tokens=chunk_size_tokens, overlap_tokens=overlap_tokens)

    return [
        build_chunk(
            source=source,
            chunk_text=chunk,
            chunk_index=index,
        )
        for index, chunk in enumerate(chunks)
        if chunk.strip()
    ]


def build_chunk(*, source, chunk_text: str, chunk_index: int) -> dict:
    structured_payload = {
        "canonical_source_id": str(source.id),
        "chunk_index": chunk_index,
        "source_hash": source.content_hash,
    }

    return {
        "chunk_index": chunk_index,
        "chunk_text": chunk_text,
        "token_count": estimate_tokens(chunk_text),
        "content_hash": stable_content_hash(
            content_text=chunk_text,
            structured_payload=structured_payload,
        ),
        "source_type": source.source_type,
        "source_subtype": source.source_subtype,
        "event_time": source.event_time,
        "document_id": source.document_id,
        "page_number": source.page_number,
        "section_id": source.section_id,
        "conversation_id": source.conversation_id,
        "message_id": source.message_id,
    }


def fallback_chunks(text: str, *, chunk_size_tokens: int, overlap_tokens: int) -> list[str]:
    size = max(200, chunk_size_tokens * 4)
    overlap = min(max(0, overlap_tokens * 4), size // 2)
    chunks = []
    start = 0

    while start < len(text):
        chunk = text[start : start + size]
        chunks.append(chunk)
        start += size - overlap

    return chunks
