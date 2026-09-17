from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Optional
from uuid import uuid4

from app.memory_systems.csm.models import CsmEvidence, CsmStateHistory, CsmStateVariable
from app.memory_systems.csm.v3_adapter import CsmV3Adapter
from app.memory_systems.csm.v3_engine import (
    CSM_V3_IMPLEMENTATION_VERSION,
    CSM_V3_STATE_SCHEMA_VERSION,
    allow_evidence_for_route_v3,
    allow_state_for_route_v3,
    build_measurement_trend_value,
    build_state_value_payload_v3,
    build_superseded_previous_value,
    route_query_v3,
    state_definition_for_source,
    state_key_for_source_v3,
    transition_operation_v3,
    verification_status_for_source_v3,
)


class CsmV3EngineTests(unittest.TestCase):
    def test_state_registry_only_allows_computational_state_sources(self):
        measurement = self._source(
            subtype="measurement",
            text="Measurement: Creatinine. Value: 1.4. Unit: mg/dL.",
            payload={"observation_name": "Creatinine", "value_numeric": 1.4, "unit": "mg/dL"},
        )
        document = self._source(
            source_type="document",
            subtype="section",
            text="Section heading: labs. Creatinine value appears in the document.",
            payload={"heading": "labs"},
        )
        encounter = self._source(
            subtype="encounter",
            text="Encounter type: outpatient.",
            payload={"encounter_type": "outpatient", "status": "finished"},
        )

        self.assertEqual(state_definition_for_source(measurement).state_type, "measurement")
        self.assertIsNone(state_definition_for_source(document))
        self.assertIsNone(state_definition_for_source(encounter))

    def test_measurement_state_payload_preserves_numeric_unit_and_lineage(self):
        source = self._source(
            subtype="measurement",
            text="Measurement: Potassium. Value: 4.9. Unit: mmol/L.",
            payload={"observation_name": "Potassium", "value_numeric": 4.9, "unit": "mmol/L"},
        )
        evidence = self._evidence(source, confidence=0.95, status="verified")
        definition = state_definition_for_source(source)

        payload = build_state_value_payload_v3(
            source=source,
            evidence=evidence,
            definition=definition,
            operation="initialize",
            version=1,
            previous_value=None,
            supersedes=[],
            dependency_ids=["dep-1"],
        )

        self.assertEqual(payload["schema_version"], CSM_V3_STATE_SCHEMA_VERSION)
        self.assertEqual(payload["implementation_version"], CSM_V3_IMPLEMENTATION_VERSION)
        self.assertEqual(payload["state_identity"]["state_key"], state_key_for_source_v3(source))
        self.assertEqual(payload["value"]["value_numeric"], 4.9)
        self.assertEqual(payload["unit"], "mmol/L")
        self.assertEqual(payload["support_evidence_ids"], [str(evidence.id)])
        self.assertEqual(payload["dependency_ids"], ["dep-1"])

    def test_correction_creates_corrects_relation_and_superseded_previous_value(self):
        original = self._source(
            subtype="measurement",
            text="Measurement: Potassium. Value: 5.8. Unit: mmol/L.",
            payload={"observation_name": "Potassium", "value_numeric": 5.8, "unit": "mmol/L"},
            content_hash="original",
        )
        correction = self._source(
            subtype="measurement",
            text="Corrected measurement: Potassium. Value: 4.9. Unit: mmol/L.",
            payload={"observation_name": "Potassium", "value_numeric": 4.9, "unit": "mmol/L", "status": "corrected"},
            content_hash="correction",
        )
        original_evidence = self._evidence(original, confidence=0.95, status="verified")
        correction_evidence = self._evidence(correction, confidence=0.95, status="verified")
        definition = state_definition_for_source(original)
        previous = build_state_value_payload_v3(
            source=original,
            evidence=original_evidence,
            definition=definition,
            operation="initialize",
            version=1,
            previous_value=None,
            supersedes=[],
            dependency_ids=[],
        )

        operation = transition_operation_v3(previous_value=previous, source=correction, evidence=correction_evidence)
        corrected = build_state_value_payload_v3(
            source=correction,
            evidence=correction_evidence,
            definition=definition,
            operation=operation,
            version=2,
            previous_value=previous,
            supersedes=previous["evidence_ids"],
            dependency_ids=[],
        )
        superseded_previous = build_superseded_previous_value(previous, evidence_id=str(correction_evidence.id), operation=operation)

        self.assertEqual(operation, "correct")
        self.assertEqual(corrected["relations"]["incoming_relation"], "CORRECTS")
        self.assertEqual(corrected["relations"]["supersedes"], [str(original_evidence.id)])
        self.assertEqual(superseded_previous["status"], "superseded")
        self.assertIn(str(correction_evidence.id), superseded_previous["relations"]["superseded_by"])

    def test_current_retrieval_excludes_superseded_but_correction_route_allows_it(self):
        now = datetime(2026, 6, 1, tzinfo=timezone.utc)
        state = CsmStateVariable(
            id=uuid4(),
            system_instance_id=uuid4(),
            state_type="measurement",
            state_key="measurement:potassium",
            current_value={
                "implementation_version": CSM_V3_IMPLEMENTATION_VERSION,
                "status": "superseded",
                "recorded_time": now.isoformat(),
            },
            confidence=0.9,
            uncertainty={},
            status="stale",
            valid_from=now,
            valid_to=None,
            current_version=2,
            update_operator="test",
            last_updated_at=now,
        )

        allowed_current, current_reason = allow_state_for_route_v3(
            state=state,
            route=route_query_v3("What is the current potassium?"),
            cutoff_time=now,
        )
        allowed_history, history_reason = allow_state_for_route_v3(
            state=state,
            route=route_query_v3("What was the corrected superseded potassium value?"),
            cutoff_time=now,
        )

        self.assertFalse(allowed_current)
        self.assertEqual(current_reason, "superseded_excluded_for_current_query")
        self.assertTrue(allowed_history)
        self.assertEqual(history_reason, "allowed")

    def test_future_recorded_evidence_cannot_pass_cutoff_filter(self):
        source = self._source(
            subtype="measurement",
            text="Measurement: Creatinine. Value: 1.2. Unit: mg/dL.",
            payload={"observation_name": "Creatinine", "value_numeric": 1.2, "unit": "mg/dL"},
            recorded=datetime(2026, 6, 3, tzinfo=timezone.utc),
        )
        evidence = self._evidence(source, confidence=0.95, status="verified")
        route = route_query_v3("What is the creatinine?")

        allowed, reason = allow_evidence_for_route_v3(
            evidence=evidence,
            route=route,
            cutoff_time=datetime(2026, 6, 2, tzinfo=timezone.utc),
        )

        self.assertFalse(allowed)
        self.assertEqual(reason, "recorded_after_source_cutoff")

    def test_conversation_claims_remain_pending_review_not_verified_state(self):
        source = self._source(
            source_type="conversation",
            subtype="user_message",
            text="I think I am allergic to amoxicillin.",
            payload={"role": "user"},
        )

        self.assertIsNone(state_definition_for_source(source))
        self.assertEqual(verification_status_for_source_v3(source), "pending_review")

    def test_measurement_history_builds_derived_trend(self):
        state = self._state("measurement:creatinine", value_numeric=1.5, valid_time=datetime(2026, 6, 2, tzinfo=timezone.utc))
        histories = [
            self._history(state, version=1, value_numeric=1.8, valid_time=datetime(2026, 6, 1, tzinfo=timezone.utc)),
            self._history(state, version=2, value_numeric=1.5, valid_time=datetime(2026, 6, 2, tzinfo=timezone.utc)),
        ]

        trend = build_measurement_trend_value(state, histories)

        self.assertEqual(trend["direction"], "decreasing")
        self.assertEqual(trend["previous_value"], 1.8)
        self.assertEqual(trend["latest_value"], 1.5)

    def test_mandatory_candidates_survive_optional_top_k(self):
        adapter = CsmV3Adapter()
        state = SimpleNamespace(id=uuid4())
        mandatory = {
            "kind": "state",
            "state": state,
            "evidence": None,
            "score": 0.20,
            "components": {},
            "reason": "mandatory",
            "content": "mandatory",
            "token_count": 1,
            "mandatory": True,
        }
        optional = [
            {
                "kind": "state",
                "state": SimpleNamespace(id=uuid4()),
                "evidence": None,
                "score": 0.99,
                "components": {},
                "reason": "optional",
                "content": f"optional {index}",
                "token_count": 1,
                "mandatory": False,
            }
            for index in range(10)
        ]

        selected = adapter.select_activation_candidates(
            state_candidates=[mandatory, *optional],
            evidence_candidates=[],
            route_mode="state_first",
            token_budget=100,
        )

        self.assertIn(mandatory, selected)
        self.assertLessEqual(len([item for item in selected if not item["mandatory"]]), 4)

    def _source(
        self,
        *,
        subtype: str,
        text: str,
        payload: dict,
        source_type: str = "patient_information",
        content_hash: str = "hash-1",
        recorded: Optional[datetime] = None,
    ):
        now = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
        return SimpleNamespace(
            id=uuid4(),
            patient_id=uuid4(),
            source_type=source_type,
            source_subtype=subtype,
            source_record_id=str(uuid4()),
            source_version="test",
            content_text=text,
            structured_payload=payload,
            content_hash=content_hash,
            event_time=now,
            valid_time=now,
            recorded_time=recorded or now,
            document_id=None,
            page_number=None,
            section_id=None,
            conversation_id=None,
            message_id=None,
        )

    def _evidence(self, source, *, confidence: float, status: str) -> CsmEvidence:
        return CsmEvidence(
            id=uuid4(),
            system_instance_id=uuid4(),
            canonical_source_id=source.id,
            evidence_type=f"structured_{source.source_subtype}",
            observation_type=source.source_subtype,
            content=source.content_text,
            structured_value={
                **source.structured_payload,
                "csm_implementation_version": CSM_V3_IMPLEMENTATION_VERSION,
                "csm_v3_lifecycle": "current",
            },
            normalized_value="test",
            unit=source.structured_payload.get("unit"),
            source_type=source.source_type,
            document_id=None,
            page_number=None,
            section_id=None,
            conversation_id=None,
            message_id=None,
            valid_time=source.valid_time,
            recorded_time=source.recorded_time,
            confidence=confidence,
            verification_status=status,
            extraction_method="test",
            extractor_version="3",
            is_active=True,
        )

    def _state(self, key: str, *, value_numeric: float, valid_time: datetime) -> CsmStateVariable:
        return CsmStateVariable(
            id=uuid4(),
            system_instance_id=uuid4(),
            state_type="measurement",
            state_key=key,
            current_value={
                "implementation_version": CSM_V3_IMPLEMENTATION_VERSION,
                "value": {
                    "observation_name": "Creatinine",
                    "value_numeric": value_numeric,
                    "unit": "mg/dL",
                },
                "structured": {
                    "observation_name": "Creatinine",
                    "value_numeric": value_numeric,
                    "unit": "mg/dL",
                },
                "valid_time": valid_time.isoformat(),
            },
            confidence=0.95,
            uncertainty={},
            status="active",
            valid_from=valid_time,
            valid_to=None,
            current_version=2,
            update_operator="test",
            last_updated_at=valid_time,
        )

    def _history(self, state: CsmStateVariable, *, version: int, value_numeric: float, valid_time: datetime) -> CsmStateHistory:
        return CsmStateHistory(
            id=uuid4(),
            state_variable_id=state.id,
            version_number=version,
            previous_value=None,
            new_value={
                "implementation_version": CSM_V3_IMPLEMENTATION_VERSION,
                "value": {
                    "observation_name": "Creatinine",
                    "value_numeric": value_numeric,
                    "unit": "mg/dL",
                },
                "structured": {
                    "observation_name": "Creatinine",
                    "value_numeric": value_numeric,
                    "unit": "mg/dL",
                },
                "valid_time": valid_time.isoformat(),
            },
            previous_confidence=None,
            new_confidence=0.95,
            update_reason="test",
            valid_from=valid_time,
            valid_to=None,
            update_event_id=None,
            created_at=valid_time,
        )


if __name__ == "__main__":
    unittest.main()
