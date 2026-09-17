from __future__ import annotations


JOB_TYPES = {
    "verify_upload",
    "detect_file_type",
    "calculate_checksum",
    "extract_text",
    "build_pages",
    "build_sections",
    "persist_artifacts",
    "classify_ocr_requirement",
    "process_document",
}

JOB_STATUSES = {
    "queued",
    "running",
    "succeeded",
    "failed",
    "retry_scheduled",
    "cancelled",
    "dead_lettered",
}

ARTIFACT_TYPES = {
    "raw_extracted_text",
    "normalized_text",
    "processing_metadata",
    "page_text_bundle",
    "section_text_bundle",
}
