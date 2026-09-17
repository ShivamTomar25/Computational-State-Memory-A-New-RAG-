from __future__ import annotations


DOCUMENT_TYPES = {
    "lab_report",
    "prescription",
    "discharge_summary",
    "imaging_report",
    "consultation_note",
    "referral",
    "procedure_report",
    "insurance_document",
    "identity_document",
    "consent_form",
    "clinical_note_attachment",
    "other",
}

SOURCE_TYPES = {
    "doctor_upload",
    "patient_provided",
    "external_import",
}

INTERNAL_SOURCE_TYPES = {
    "system_generated",
    "derived_artifact",
}

UPLOAD_STATUSES = {
    "pending_upload",
    "upload_in_progress",
    "uploaded",
    "upload_failed",
    "expired",
    "cancelled",
}

VERIFICATION_STATUSES = {
    "not_started",
    "verifying",
    "verified",
    "failed",
    "rejected",
}

PROCESSING_STATUSES = {
    "not_started",
    "queued",
    "processing",
    "completed",
    "partially_completed",
    "failed",
    "cancelled",
    "awaiting_ocr",
}

TEXT_EXTRACTION_STATUSES = {
    "not_started",
    "queued",
    "extracting",
    "extracted",
    "no_text_found",
    "low_quality_text",
    "failed",
    "not_supported",
    "awaiting_ocr",
}

OCR_REQUIREMENT_STATUSES = {
    "not_evaluated",
    "not_required",
    "likely_required",
    "required",
    "mixed_document",
    "unsupported",
}

QUALITY_STATUSES = {
    "good",
    "acceptable",
    "low",
    "unusable",
}

AUDIT_ACTIONS = {
    "upload_initiated",
    "upload_completed",
    "upload_cancelled",
    "upload_expired",
    "upload_verification_started",
    "upload_verified",
    "upload_rejected",
    "processing_queued",
    "processing_started",
    "text_extracted",
    "ocr_required",
    "processing_completed",
    "processing_failed",
    "view_url_generated",
    "download_url_generated",
    "archived",
    "restored",
    "superseded",
    "metadata_updated",
}
