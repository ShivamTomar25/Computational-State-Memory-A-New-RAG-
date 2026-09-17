from __future__ import annotations

from app.config import settings
from app.llm.common.exceptions.errors import LlmDataEgressBlocked
from app.llm.common.schemas.answer import LlmContextBlock
from app.llm.common.safety.redaction import deidentify_text


def sanitize_for_external_llm(
    *,
    question: str,
    context: list[LlmContextBlock],
    history: list[dict],
    patient,
) -> tuple[str, list[LlmContextBlock], list[dict], dict]:
    mode = settings.llm_external_data_mode

    if mode == "disabled":
        raise LlmDataEgressBlocked("External LLM data egress is disabled.")

    if mode == "synthetic_only" and not settings.llm_allow_identifiable_clinical_data:
        raise LlmDataEgressBlocked("Synthetic-only LLM mode blocks patient-scoped requests.")

    if settings.llm_allow_identifiable_clinical_data:
        return question, context, history, {"mode": mode, "deidentified": False}

    fields = {
        "patient_name": getattr(patient, "full_name", "") or "",
        "email": getattr(patient, "email", "") or "",
        "phone": getattr(patient, "phone", "") or "",
        "address": getattr(patient, "address", "") or "",
    }
    question_result = deidentify_text(question, **fields)
    clean_context = [
        item.model_copy(update={"content": deidentify_text(item.content, **fields).text})
        for item in context
    ]
    clean_history = [
        {
            **message,
            "content": deidentify_text(str(message.get("content", "")), **fields).text,
        }
        for message in history
    ]

    return question_result.text, clean_context, clean_history, {"mode": mode, "deidentified": True}
