from __future__ import annotations

import hashlib

from sqlalchemy.orm import Session

from app.config import settings
from app.llm.common.exceptions.errors import LlmStructuredOutputFailed
from app.llm.common.schemas.answer import LlmProviderRequest
from app.memory_systems.rolling_summary.exceptions.errors import RollingSummaryCitationError
from app.memory_systems.rolling_summary.prompts.summary_prompt import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_user_prompt,
)
from app.memory_systems.rolling_summary.provider.groq_provider import RollingSummaryGroqProvider
from app.memory_systems.rolling_summary.repository.snapshots import create_snapshot, next_version_number
from app.memory_systems.rolling_summary.schemas.summary import RollingSummaryDocument
from app.memory_systems.rolling_summary.validators.citations import validate_summary_citations


class RollingSummaryService:
    def __init__(self, provider: RollingSummaryGroqProvider | None = None) -> None:
        self.provider = provider or RollingSummaryGroqProvider()

    def provider_status(self) -> str:
        return self.provider.status()

    def update_summary(self, db: Session, *, instance, sources: list) -> None:
        if not sources:
            return

        source_payloads = [serialize_source(source) for source in sources]
        source_cutoff_time = max(source.event_time for source in sources)
        input_hash = hash_sources(source_payloads)
        prompt = build_user_prompt(
            source_cutoff_time=source_cutoff_time.isoformat(),
            sources=source_payloads,
        )
        request = LlmProviderRequest(
            task_type="rolling_summary",
            system_prompt=SYSTEM_PROMPT,
            user_prompt=prompt,
            context=[],
            model_configuration={
                "provider": settings.llm_provider,
                "model": settings.groq_model,
                "temperature": 0,
            },
            trace_metadata={
                "system_instance_id": str(instance.id),
                "system_type": instance.system_type,
            },
        )
        summarizer_provider = settings.llm_provider
        summarizer_model = settings.groq_model

        allowed_ids = {payload["source_id"] for payload in source_payloads}

        try:
            result = self.provider.summarize(request)
            summary = RollingSummaryDocument.model_validate(result.structured_value)
            validate_summary_citations(summary, allowed_ids)
        except (LlmStructuredOutputFailed, RollingSummaryCitationError):
            summary = build_extractive_summary(source_payloads, source_cutoff_time.isoformat())
            summarizer_provider = "deterministic_extractive_fallback"
            summarizer_model = "source_text"
            validate_summary_citations(summary, allowed_ids)

        create_snapshot(
            db,
            data={
                "system_instance_id": instance.id,
                "version_number": next_version_number(db, system_instance_id=instance.id),
                "summary_text": summary.render_text(),
                "summary_status": "ready",
                "covered_cutoff_time": source_cutoff_time,
                "input_hash": input_hash,
                "source_count": len(sources),
                "summarizer_provider": summarizer_provider,
                "summarizer_model": summarizer_model,
                "prompt_version": PROMPT_VERSION,
            },
            source_ids=[source.id for source in sources],
        )


def serialize_source(source) -> dict:
    return {
        "source_id": str(source.id),
        "source_type": source.source_type,
        "source_subtype": source.source_subtype,
        "event_time": source.event_time.isoformat(),
        "content": " ".join(source.content_text.split()),
    }


def hash_sources(sources: list[dict]) -> str:
    payload = "\n".join(
        f"{source['source_id']}|{source['event_time']}|{source['content']}"
        for source in sources
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_extractive_summary(sources: list[dict], source_cutoff_time: str) -> RollingSummaryDocument:
    sections = {
        "patient_overview": [],
        "active_conditions": [],
        "medications": [],
        "allergies": [],
        "measurements": [],
        "recent_clinical_events": [],
        "unresolved_questions": [],
        "contradictions": [],
        "uncertainty": [],
    }

    for source in sources:
        subtype = (source.get("source_subtype") or "").lower()
        target = "recent_clinical_events"

        if "condition" in subtype:
            target = "active_conditions"
        elif "medication" in subtype:
            target = "medications"
        elif "allerg" in subtype:
            target = "allergies"
        elif "measurement" in subtype or "lab" in subtype:
            target = "measurements"
        elif "conflict" in subtype or "contradiction" in source.get("content", "").lower():
            target = "contradictions"
        elif "note" in subtype or "encounter" in subtype or "document" in source.get("source_type", ""):
            target = "recent_clinical_events"

        sections[target].append(source)

    all_text = " ".join(source.get("content", "") for source in sources)
    sections["patient_overview"] = sources[:5] if all_text else []

    return RollingSummaryDocument(
        patient_overview=render_section(sections["patient_overview"], "Available source summary"),
        active_conditions=render_section(sections["active_conditions"], "Condition evidence"),
        medications=render_section(sections["medications"], "Medication evidence"),
        allergies=render_section(sections["allergies"], "Allergy evidence"),
        measurements=render_section(sections["measurements"], "Measurement evidence"),
        recent_clinical_events=render_section(sections["recent_clinical_events"], "Recent clinical evidence"),
        unresolved_questions=render_section(sections["unresolved_questions"], "No unresolved questions extracted"),
        contradictions=render_section(sections["contradictions"], "Contradiction evidence"),
        uncertainty=render_section(sections["uncertainty"], "No additional uncertainty extracted"),
        covered_source_ids=[source["source_id"] for source in sources],
        source_cutoff_time=source_cutoff_time,
    )


def render_section(sources: list[dict], empty_text: str):
    from app.memory_systems.rolling_summary.schemas.summary import RollingSummaryCitation, RollingSummarySection

    if not sources:
        return RollingSummarySection(text=empty_text, citations=[])

    snippets = []
    citations = []

    for source in sources[:8]:
        content = " ".join((source.get("content") or "").split())

        if content:
            snippets.append(content[:220])
            citations.append(RollingSummaryCitation(source_id=source["source_id"], claim=content[:180]))

    return RollingSummarySection(text=" ".join(snippets)[:1200], citations=citations)
