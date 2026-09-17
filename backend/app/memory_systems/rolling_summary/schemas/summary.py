from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class RollingSummaryCitation(BaseModel):
    source_id: str
    claim: str = Field(min_length=1)


class RollingSummarySection(BaseModel):
    text: str = ""
    citations: list[RollingSummaryCitation] = Field(default_factory=list)


class RollingSummaryDocument(BaseModel):
    patient_overview: RollingSummarySection
    active_conditions: RollingSummarySection
    medications: RollingSummarySection
    allergies: RollingSummarySection
    measurements: RollingSummarySection
    recent_clinical_events: RollingSummarySection
    unresolved_questions: RollingSummarySection
    contradictions: RollingSummarySection
    uncertainty: RollingSummarySection
    covered_source_ids: list[str] = Field(default_factory=list)
    source_cutoff_time: Optional[str] = None

    def render_text(self) -> str:
        sections = [
            ("Patient overview", self.patient_overview.text),
            ("Active conditions", self.active_conditions.text),
            ("Medications", self.medications.text),
            ("Allergies", self.allergies.text),
            ("Measurements", self.measurements.text),
            ("Recent clinical events", self.recent_clinical_events.text),
            ("Unresolved questions", self.unresolved_questions.text),
            ("Contradictions", self.contradictions.text),
            ("Uncertainty", self.uncertainty.text),
        ]

        return "\n\n".join(
            f"{title}: {text.strip() or 'None stated.'}"
            for title, text in sections
        )
