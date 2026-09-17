from __future__ import annotations

from app.memory_systems.rolling_summary.exceptions.errors import RollingSummaryCitationError
from app.memory_systems.rolling_summary.schemas.summary import RollingSummaryDocument


def validate_summary_citations(summary: RollingSummaryDocument, allowed_source_ids: set[str]) -> None:
    cited_ids = set(summary.covered_source_ids)

    for section in [
        summary.patient_overview,
        summary.active_conditions,
        summary.medications,
        summary.allergies,
        summary.measurements,
        summary.recent_clinical_events,
        summary.unresolved_questions,
        summary.contradictions,
        summary.uncertainty,
    ]:
        cited_ids.update(citation.source_id for citation in section.citations)

    invalid_ids = sorted(source_id for source_id in cited_ids if source_id not in allowed_source_ids)

    if invalid_ids:
        raise RollingSummaryCitationError(
            f"Rolling summary cited unavailable sources: {', '.join(invalid_ids)}"
        )
