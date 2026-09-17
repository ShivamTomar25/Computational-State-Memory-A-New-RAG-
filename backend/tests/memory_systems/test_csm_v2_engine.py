from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.memory_systems.csm.models import CsmEvidence
from app.memory_systems.csm.v2_engine import (
    CSM_V2_STATE_SCHEMA_VERSION,
    build_state_value_payload,
    route_query,
    should_supersede,
    state_key_for_source_v2,
)


class CsmV2EngineTests(unittest.TestCase):
    def test_routes_correction_queries_without_patient_specific_values(self):
        route = route_query("Which potassium value should be used after the amended lab addendum?")

        self.assertEqual(route.mode, "correction_state")
        self.assertIn("correction", route.reason)
        self.assertIn("measurement", route.preferred_state_types)

    def test_builds_generic_versioned_state_payload(self):
        source = self._source(
            text="Measurement: Potassium. Value: 4.9. Unit: mmol/L.",
            payload={"observation_name": "Potassium", "value_numeric": 4.9, "unit": "mmol/L"},
        )
        evidence = self._evidence(source, confidence=0.93, status="verified")

        payload = build_state_value_payload(
            source=source,
            evidence=evidence,
            operation="upsert",
            version=1,
            previous_value=None,
            supersedes=[],
            dependency_ids=["dep-test-1"],
        )

        self.assertEqual(payload["schema_version"], CSM_V2_STATE_SCHEMA_VERSION)
        self.assertEqual(payload["state_identity"]["semantic_type"], "measurement")
        self.assertEqual(payload["state_identity"]["state_key"], state_key_for_source_v2(source))
        self.assertEqual(payload["unit"], "mmol/L")
        self.assertEqual(payload["dependency_ids"], ["dep-test-1"])
        self.assertEqual(payload["lineage"]["latest_canonical_source_id"], str(source.id))

    def test_supersession_is_generic_same_key_newer_source(self):
        original = self._source(
            text="Measurement: Potassium. Value: 5.8. Unit: mmol/L.",
            payload={"observation_name": "Potassium", "value_numeric": 5.8, "unit": "mmol/L"},
            content_hash="original-hash",
        )
        revised = self._source(
            text="Measurement: Potassium. Value: 4.9. Unit: mmol/L.",
            payload={"observation_name": "Potassium", "value_numeric": 4.9, "unit": "mmol/L"},
            content_hash="revised-hash",
        )
        original_evidence = self._evidence(original, confidence=0.91, status="verified")
        revised_evidence = self._evidence(revised, confidence=0.92, status="verified")
        previous = build_state_value_payload(
            source=original,
            evidence=original_evidence,
            operation="upsert",
            version=1,
            previous_value=None,
            supersedes=[],
            dependency_ids=[],
        )

        self.assertTrue(should_supersede(previous, revised, revised_evidence))

    def _source(self, *, text: str, payload: dict, content_hash: str = "hash-1"):
        now = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
        return SimpleNamespace(
            id=uuid4(),
            source_type="patient_information",
            source_subtype="measurement",
            source_record_id=str(uuid4()),
            source_version="test",
            content_text=text,
            structured_payload=payload,
            content_hash=content_hash,
            event_time=now,
            valid_time=now,
            recorded_time=now,
            document_id=None,
            page_number=None,
            section_id=None,
        )

    def _evidence(self, source, *, confidence: float, status: str) -> CsmEvidence:
        return CsmEvidence(
            id=uuid4(),
            system_instance_id=uuid4(),
            canonical_source_id=source.id,
            evidence_type="structured_measurement",
            observation_type="measurement",
            content=source.content_text,
            structured_value=source.structured_payload,
            normalized_value="potassium",
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
            extractor_version="2",
            is_active=True,
        )


if __name__ == "__main__":
    unittest.main()
