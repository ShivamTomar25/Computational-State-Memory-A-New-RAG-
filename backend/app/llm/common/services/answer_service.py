from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.llm.common.exceptions.errors import LlmError, LlmNotConfigured
from app.llm.common.prompts.registry import prompt_registry
from app.llm.common.repositories import llm_repository
from app.llm.common.safety.data_egress import sanitize_for_external_llm
from app.llm.common.schemas.answer import GroundedAnswer, LlmContextBlock, LlmProviderRequest
from app.llm.common.structured_output.citations import validate_answer_citations
from app.llm.providers.factory import get_chat_provider


@dataclass
class AnswerGenerationOutcome:
    status: str
    answer: Optional[GroundedAnswer]
    llm_call_id: Optional[str]
    provider: Optional[str]
    model: Optional[str]
    prompt_version: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    duration_ms: int
    warnings: list[str]
    error_code: Optional[str] = None
    error_reason: Optional[str] = None


def generate_grounded_answer(
    db: Session,
    *,
    patient,
    instance,
    conversation,
    retrieval,
    conversation_history: list,
    question: str,
    generation_options: Optional[dict] = None,
) -> AnswerGenerationOutcome:
    provider = get_chat_provider()
    prompt = prompt_registry.get_final_answer_prompt()

    if provider.health() in {"not_configured", "disabled"}:
        return AnswerGenerationOutcome(
            status="not_configured",
            answer=None,
            llm_call_id=None,
            provider=provider.model_metadata().get("provider"),
            model=provider.model_metadata().get("model"),
            prompt_version=prompt.version,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            duration_ms=0,
            warnings=["LLM provider is not configured. No assistant answer was generated."],
        )

    context = build_context_blocks(retrieval.context_items)
    history = build_history(conversation_history)

    try:
        clean_question, clean_context, clean_history, egress_metadata = sanitize_for_external_llm(
            question=question,
            context=context,
            history=history,
            patient=patient,
        )
    except LlmError as error:
        return AnswerGenerationOutcome(
            status="blocked",
            answer=None,
            llm_call_id=None,
            provider=provider.model_metadata().get("provider"),
            model=provider.model_metadata().get("model"),
            prompt_version=prompt.version,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            duration_ms=0,
            warnings=[str(error)],
            error_code=error.__class__.__name__,
            error_reason=str(error),
        )

    user_prompt = prompt.user_prompt_template.format(
        question=clean_question,
        conversation_history=format_history(clean_history),
        context=format_context(clean_context),
    )
    call = llm_repository.create_llm_call(
        db,
        data={
            "patient_id": patient.id,
            "system_instance_id": instance.id,
            "conversation_id": conversation.id,
            "retrieval_run_id": retrieval.retrieval_run_id,
            "ingestion_run_id": None,
            "task_type": "final_answer",
            "provider": provider.model_metadata().get("provider", settings.llm_provider),
            "model": provider.model_metadata().get("model", settings.groq_model),
            "prompt_id": prompt.prompt_id,
            "prompt_version": prompt.version,
            "prompt_hash": prompt.checksum,
            "request_status": "running",
            "data_egress_mode": settings.llm_external_data_mode,
            "safe_metadata": {
                "system_type": instance.system_type,
                "context_count": len(clean_context),
                "deidentified": egress_metadata.get("deidentified", False),
            },
        },
    )
    request = LlmProviderRequest(
        task_type="final_answer",
        system_prompt=prompt.system_prompt,
        user_prompt=user_prompt,
        message_history=clean_history,
        context=clean_context,
        model_configuration={**provider.model_metadata(), **(generation_options or {})},
        trace_metadata={
            "llm_call_id": str(call.id),
            "system_instance_id": str(instance.id),
            "conversation_id": str(conversation.id),
        },
    )

    structured_output_attempts = []

    try:
        provider_result = provider.invoke_structured(request, GroundedAnswer)
        validated = validate_answer_citations(
            provider_result.structured_value,
            clean_context,
        )
        warnings = list(provider_result.warnings)

        if validated.invalid_citation_ids:
            warnings.append("One or more fabricated citation IDs were removed from the answer.")

        llm_repository.complete_llm_call(
            db,
            call=call,
            data={
                "request_status": "completed",
                "input_token_count": provider_result.input_tokens,
                "output_token_count": provider_result.output_tokens,
                "total_token_count": provider_result.total_tokens,
                "duration_ms": provider_result.duration_ms,
                "retry_count": provider_result.retry_count,
                "finish_reason": provider_result.finish_reason,
                "safe_metadata": {
                    **call.safe_metadata,
                    "invalid_citation_count": len(validated.invalid_citation_ids),
                    "request_identifier_present": bool(provider_result.request_identifier),
                    **provider_result.metadata,
                },
            },
        )

        return AnswerGenerationOutcome(
            status="completed",
            answer=validated.answer,
            llm_call_id=str(call.id),
            provider=provider_result.provider,
            model=provider_result.model,
            prompt_version=prompt.version,
            input_tokens=provider_result.input_tokens,
            output_tokens=provider_result.output_tokens,
            total_tokens=provider_result.total_tokens,
            duration_ms=provider_result.duration_ms,
            warnings=warnings,
        )
    except LlmNotConfigured as error:
        status = "not_configured"
        error_code = error.__class__.__name__
        error_reason = str(error)
        structured_output_attempts = getattr(error, "structured_output_attempts", [])
    except LlmError as error:
        status = "failed"
        error_code = error.__class__.__name__
        error_reason = str(error)
        structured_output_attempts = getattr(error, "structured_output_attempts", [])
    except Exception as error:
        status = "failed"
        error_code = error.__class__.__name__
        error_reason = "LLM answer generation failed."
        structured_output_attempts = getattr(error, "structured_output_attempts", [])

    llm_repository.complete_llm_call(
        db,
        call=call,
        data={
            "request_status": status,
            "error_code": error_code,
            "error_reason": error_reason,
            "safe_metadata": {
                **call.safe_metadata,
                **({"structured_output_attempts": structured_output_attempts} if structured_output_attempts else {}),
            },
        },
    )

    return AnswerGenerationOutcome(
        status=status,
        answer=None,
        llm_call_id=str(call.id),
        provider=provider.model_metadata().get("provider"),
        model=provider.model_metadata().get("model"),
        prompt_version=prompt.version,
        input_tokens=0,
        output_tokens=0,
        total_tokens=0,
        duration_ms=0,
        warnings=[error_reason],
        error_code=error_code,
        error_reason=error_reason,
    )


def build_context_blocks(items) -> list[LlmContextBlock]:
    blocks = []

    for index, item in enumerate(items, start=1):
        blocks.append(
            LlmContextBlock(
                citation_id=f"C{index}",
                source_type=item.source_type,
                event_time=item.event_time,
                canonical_source_id=item.canonical_source_id,
                document_id=item.document_id,
                page_number=item.page_number,
                section_id=item.section_id,
                confidence=item.score,
                content=item.content or item.content_preview,
            )
        )

    return blocks


def build_history(messages) -> list[dict]:
    return [
        {
            "role": message.role,
            "content": message.content,
            "event_time": message.event_time.isoformat() if message.event_time else None,
        }
        for message in messages[-12:]
    ]


def format_history(history: list[dict]) -> str:
    if not history:
        return "No prior messages."

    return "\n".join(
        f"{message['role']}: {message['content']}"
        for message in history
    )


def format_context(context: list[LlmContextBlock]) -> str:
    if not context:
        return "No retrieved context."

    blocks = []

    for item in context:
        blocks.append(
            "\n".join(
                [
                    "[CONTEXT ITEM]",
                    f"citation_id: {item.citation_id}",
                    f"source_type: {item.source_type or 'unknown'}",
                    f"event_time: {item.event_time.isoformat() if item.event_time else 'unknown'}",
                    f"canonical_source_id: {item.canonical_source_id or 'none'}",
                    f"document_id: {item.document_id or 'none'}",
                    f"page_number: {item.page_number or 'none'}",
                    f"section_id: {item.section_id or 'none'}",
                    f"confidence: {item.confidence if item.confidence is not None else 'unknown'}",
                    "content:",
                    item.content,
                    "[/CONTEXT ITEM]",
                ]
            )
        )

    return "\n\n".join(blocks)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
