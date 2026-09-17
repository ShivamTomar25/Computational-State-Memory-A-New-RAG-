from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.config import settings
from app.memory_systems.common.enums.status import SYSTEM_METADATA, SYSTEM_TYPES
from app.memory_systems.common.registry.registry import registry
from app.memory_systems.csm.models import CsmEvidence, CsmStateEvidenceLink, CsmStateVariable
from app.memory_systems.csm.v4_adapter import CsmV4Adapter, evidence_recorded_time_v4
from app.memory_systems.csm.v4_engine import (
    CSM_V4_IMPLEMENTATION_VERSION,
    allow_evidence_for_route_v4,
    compact_state_context_v4,
    explicit_date_match,
    late_arriving_temporal_match,
    route_query_v4,
)


class CsmV4EngineTests(unittest.TestCase):
    def test_csm_v4_is_registered_as_separate_system(self):
        self.assertIn("csm_v4", SYSTEM_TYPES)
        self.assertEqual(registry.get("csm_v4").system_type, "csm_v4")
        self.assertEqual(SYSTEM_METADATA["csm_v4"]["display_name"], "CSM v4")

    def test_route_token_budgets_are_adaptive(self):
        adapter = CsmV4Adapter()

        state_route = route_query_v4("List active clinical problems medications allergies and measurements for this patient")
        correction_route = route_query_v4("What corrected superseded potassium value replaced the old result?")
        summary_route = route_query_v4("Summarize overall clinical course across conditions medications allergies measurements")

        self.assertEqual(state_route.mode, "state_first")
        self.assertEqual(adapter.route_token_budget(route=state_route, requested_token_budget=10_000), settings.csm_v4_simple_state_token_budget)
        self.assertEqual(correction_route.mode, "correction_state")
        self.assertEqual(adapter.route_token_budget(route=correction_route, requested_token_budget=10_000), settings.csm_v4_temporal_token_budget)
        self.assertEqual(summary_route.mode, "hybrid_state_evidence")
        self.assertEqual(adapter.route_token_budget(route=summary_route, requested_token_budget=10_000), settings.csm_v4_summary_token_budget)

    def test_route_result_limits_allow_broader_temporal_and_exact_bundles(self):
        adapter = CsmV4Adapter()

        self.assertGreaterEqual(
            adapter.route_result_limit(route_mode="temporal_state", top_k=8, mandatory_count=0),
            settings.csm_v4_candidate_recall_limit,
        )
        self.assertGreaterEqual(
            adapter.route_result_limit(route_mode="exact_source", top_k=8, mandatory_count=0),
            settings.csm_v4_top_k_evidence,
        )
        self.assertEqual(
            adapter.route_result_limit(route_mode="state_first", top_k=8, mandatory_count=2),
            8,
        )

    def test_selected_state_gets_mandatory_support_evidence_even_below_optional_threshold(self):
        adapter = CsmV4Adapter()
        state = self._state("condition:ckd")
        evidence = self._evidence("CKD stage 3 is documented in nephrology note.")
        link = CsmStateEvidenceLink(
            state_variable_id=state.id,
            evidence_id=evidence.id,
            contribution_type="SUPPORTS",
            contribution_weight=1.0,
        )

        state_candidate = self._state_candidate(state, score=0.95, mandatory=False)
        evidence_candidate = self._evidence_candidate(evidence, score=0.01, mandatory=False)

        selected = adapter.select_activation_candidates(
            state_candidates=[state_candidate],
            evidence_candidates=[evidence_candidate],
            route_mode="state_first",
            token_budget=200,
            evidence_by_state={state.id: [(link, evidence)]},
        )

        self.assertIn(state_candidate, selected)
        self.assertIn(evidence_candidate, selected)
        self.assertTrue(evidence_candidate["mandatory"])
        self.assertEqual(evidence_candidate["lineage_role"], "mandatory_state_support_evidence")

    def test_correction_route_preserves_correction_evidence_after_support_limit(self):
        adapter = CsmV4Adapter()
        state = self._state("measurement:potassium")
        state_candidate = self._state_candidate(state, score=0.95, mandatory=True)
        evidences = [self._evidence(f"Support evidence {index}") for index in range(4)]
        evidence_candidates = [self._evidence_candidate(evidence, score=0.01, mandatory=False) for evidence in evidences]
        links = [
            (
                CsmStateEvidenceLink(
                    state_variable_id=state.id,
                    evidence_id=evidence.id,
                    contribution_type="CORRECTS" if index == 3 else "SUPPORTS",
                    contribution_weight=1.0,
                ),
                evidence,
            )
            for index, evidence in enumerate(evidences)
        ]

        selected = adapter.select_activation_candidates(
            state_candidates=[state_candidate],
            evidence_candidates=evidence_candidates,
            route_mode="correction_state",
            token_budget=500,
            evidence_by_state={state.id: links},
        )

        selected_evidence = [item for item in selected if item["evidence"] is not None]
        correction_candidate = evidence_candidates[3]
        self.assertEqual(len(selected_evidence), 4)
        self.assertIn(correction_candidate, selected)
        self.assertEqual(correction_candidate["lineage_role"], "mandatory_correction_evidence")

    def test_route_mandatory_retraction_evidence_gets_correction_lineage_role(self):
        adapter = CsmV4Adapter()
        evidence = self._evidence("Correction notice: the imported statement is retracted.")
        evidence_candidate = self._evidence_candidate(evidence, score=0.95, mandatory=True)

        selected = adapter.select_activation_candidates(
            state_candidates=[],
            evidence_candidates=[evidence_candidate],
            route_mode="correction_state",
            token_budget=100,
            evidence_by_state={},
        )

        self.assertIn(evidence_candidate, selected)
        self.assertEqual(evidence_candidate["lineage_role"], "mandatory_correction_evidence")

    def test_temporal_route_uses_evidence_fallback_and_measurement_evidence(self):
        route = route_query_v4("What was the creatinine on 2026-06-01?")

        self.assertEqual(route.mode, "temporal_state")
        self.assertTrue(route.include_historical)
        self.assertTrue(route.evidence_fallback)
        self.assertIn("structured_measurement", route.preferred_evidence_types)

    def test_explicit_date_match_supports_named_dates(self):
        self.assertTrue(explicit_date_match("What does the 22 April follow-up show?", datetime(2026, 4, 22, tzinfo=timezone.utc)))
        self.assertTrue(explicit_date_match("What happened on 2026-06-01?", datetime(2026, 6, 1, tzinfo=timezone.utc)))
        self.assertFalse(explicit_date_match("What does the 22 April follow-up show?", datetime(2026, 4, 23, tzinfo=timezone.utc)))

    def test_temporal_named_date_document_evidence_is_mandatory(self):
        adapter = CsmV4Adapter()
        route = route_query_v4("What does the 22 April follow-up show?")
        evidence = self._evidence("Treatment-response follow-up report.")
        evidence.source_type = "document"
        evidence.valid_time = datetime(2026, 4, 22, tzinfo=timezone.utc)

        self.assertTrue(adapter.is_temporal_date_evidence(route=route, query="What does the 22 April follow-up show?", evidence=evidence))

    def test_late_arriving_temporal_evidence_is_mandatory(self):
        adapter = CsmV4Adapter()
        route = route_query_v4("Which event occurred before the 5 March specimen but was recorded later?")
        evidence = self._evidence(
            "Dehydration note recorded later.",
            recorded_time=datetime(2026, 3, 10, tzinfo=timezone.utc),
        )
        evidence.valid_time = datetime(2026, 3, 4, tzinfo=timezone.utc)

        self.assertTrue(
            late_arriving_temporal_match(
                "Which event occurred before the 5 March specimen but was recorded later?",
                evidence.valid_time,
                evidence.recorded_time,
            )
        )
        self.assertTrue(
            adapter.is_late_arriving_temporal_evidence(
                route=route,
                query="Which event occurred before the 5 March specimen but was recorded later?",
                evidence=evidence,
            )
        )

    def test_evidence_cutoff_and_version_filters_still_apply(self):
        route = route_query_v4("What was the creatinine on 2026-06-01?")
        future_evidence = self._evidence(
            "Future creatinine evidence.",
            recorded_time=datetime(2026, 6, 3, tzinfo=timezone.utc),
        )
        old_version_evidence = self._evidence("CSM v3 evidence.")
        old_version_evidence.structured_value["csm_implementation_version"] = "csm_v3"

        allowed_future, future_reason = allow_evidence_for_route_v4(
            evidence=future_evidence,
            route=route,
            cutoff_time=datetime(2026, 6, 2, tzinfo=timezone.utc),
        )
        allowed_version, version_reason = allow_evidence_for_route_v4(
            evidence=old_version_evidence,
            route=route,
            cutoff_time=datetime(2026, 6, 2, tzinfo=timezone.utc),
        )

        self.assertFalse(allowed_future)
        self.assertEqual(future_reason, "recorded_after_source_cutoff")
        self.assertFalse(allowed_version)
        self.assertEqual(version_reason, "non_v4_evidence")

    def test_document_section_evidence_uses_parent_document_availability(self):
        document_id = uuid4()
        parent_recorded = datetime(2026, 3, 12, tzinfo=timezone.utc)
        section_extracted = datetime(2026, 7, 21, tzinfo=timezone.utc)
        db = SimpleNamespace(get=lambda model, object_id: SimpleNamespace(created_at=parent_recorded) if object_id == document_id else None)
        section_source = SimpleNamespace(
            source_type="document",
            source_subtype="section",
            document_id=document_id,
            recorded_time=section_extracted,
        )
        note_source = SimpleNamespace(
            source_type="patient_information",
            source_subtype="clinical_note",
            document_id=None,
            recorded_time=section_extracted,
        )

        self.assertEqual(evidence_recorded_time_v4(db=db, source=section_source), parent_recorded)
        self.assertEqual(evidence_recorded_time_v4(db=db, source=note_source), section_extracted)

    def test_state_context_tolerates_malformed_uncertainty(self):
        state = self._state("measurement:egfr")
        state.current_value["uncertainty_components"] = {"posterior_uncertainty": "not-a-number"}
        route = route_query_v4("What was the eGFR trend over time?")

        content = compact_state_context_v4(
            state=state,
            evidence=None,
            route=route,
            components={},
        )

        self.assertIn("[CSM_STATE]", content)
        self.assertNotIn("uncertainty: posterior=", content)

    def _state(self, key: str) -> CsmStateVariable:
        now = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
        return CsmStateVariable(
            id=uuid4(),
            system_instance_id=uuid4(),
            state_type=key.split(":", 1)[0],
            state_key=key,
            current_value={
                "implementation_version": CSM_V4_IMPLEMENTATION_VERSION,
                "state_identity": {
                    "state_type": key.split(":", 1)[0],
                    "state_key": key,
                },
                "value": {"display": key},
                "status": "active",
                "valid_time": now.isoformat(),
                "recorded_time": now.isoformat(),
                "transition": {"new_version": 1},
            },
            confidence=0.95,
            uncertainty={},
            status="active",
            valid_from=now,
            valid_to=None,
            current_version=1,
            update_operator="test",
            last_updated_at=now,
        )

    def _evidence(self, content: str, *, recorded_time: datetime | None = None) -> CsmEvidence:
        now = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
        return CsmEvidence(
            id=uuid4(),
            system_instance_id=uuid4(),
            canonical_source_id=uuid4(),
            evidence_type="structured_measurement",
            observation_type="measurement",
            content=content,
            structured_value={
                "csm_implementation_version": CSM_V4_IMPLEMENTATION_VERSION,
                "csm_v4_lifecycle": "current",
            },
            normalized_value=content.lower(),
            unit=None,
            source_type="patient_information",
            document_id=None,
            page_number=None,
            section_id=None,
            conversation_id=None,
            message_id=None,
            valid_time=now,
            recorded_time=recorded_time or now,
            confidence=0.95,
            verification_status="verified",
            extraction_method="test",
            extractor_version="4",
            is_active=True,
        )

    def _state_candidate(self, state: CsmStateVariable, *, score: float, mandatory: bool) -> dict:
        return {
            "kind": "state",
            "state": state,
            "evidence": None,
            "score": score,
            "components": {},
            "reason": "test_state",
            "content": "state content",
            "token_count": 10,
            "mandatory": mandatory,
        }

    def _evidence_candidate(self, evidence: CsmEvidence, *, score: float, mandatory: bool) -> dict:
        return {
            "kind": "evidence",
            "state": None,
            "evidence": evidence,
            "score": score,
            "components": {},
            "reason": "test_evidence",
            "content": "evidence content",
            "token_count": 10,
            "mandatory": mandatory,
        }


if __name__ == "__main__":
    unittest.main()
