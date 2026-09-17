from __future__ import annotations

from langchain_core.documents import Document as LangChainDocument


def canonical_source_to_langchain_document(source) -> LangChainDocument:
    return LangChainDocument(
        page_content=source.content_text,
        metadata={
            "canonical_source_id": str(source.id),
            "patient_id": str(source.patient_id),
            "source_type": source.source_type,
            "source_subtype": source.source_subtype,
            "source_record_id": source.source_record_id,
            "event_time": source.event_time.isoformat(),
            "valid_time": source.valid_time.isoformat() if source.valid_time else None,
            "document_id": str(source.document_id) if source.document_id else None,
            "page_number": source.page_number,
            "section_id": str(source.section_id) if source.section_id else None,
            "conversation_id": str(source.conversation_id) if source.conversation_id else None,
            "message_id": str(source.message_id) if source.message_id else None,
            "role": source.role,
            "system_instance_id": str(source.owning_system_instance_id)
            if source.owning_system_instance_id
            else None,
            "content_hash": source.content_hash,
        },
    )
