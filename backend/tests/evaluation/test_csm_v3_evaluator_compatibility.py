from types import SimpleNamespace
from unittest import TestCase

from app.evaluation.offline_recomputation.claim_matcher import ClaimMatchResult
from app.evaluation.offline_recomputation.claim_support_classifier import classify_claim
from app.evaluation.offline_recomputation.citation_resolver import resolve_citation_id
from app.evaluation.offline_recomputation.metric_calculator import aggregate_observations, systems_for_observations
from app.evaluation.offline_recomputation.state_evaluator import memory_update_accuracy
from app.evaluation.offline_recomputation.temporal_evaluator import temporal_score


class CsmV3EvaluatorCompatibilityTests(TestCase):
    def test_csm_v3_local_citation_alias_resolves_to_canonical_source(self):
        resolution = resolve_citation_id(
            "C1",
            answer_citations=[{"citation_id": "C1", "canonical_source_id": "source-1"}],
            valid_context_ids={"source-1"},
        )

        self.assertEqual(resolution.resolved_id, "source-1")
        self.assertEqual(resolution.classification, "valid_supporting")

    def test_direct_and_external_citations_keep_existing_classification(self):
        direct = resolve_citation_id("source-1", answer_citations=[], valid_context_ids={"source-1"})
        missing_local = resolve_citation_id("C99", answer_citations=[], valid_context_ids={"source-1"})
        fabricated = resolve_citation_id("made-up-reference", answer_citations=[], valid_context_ids={"source-1"})

        self.assertEqual(direct.classification, "valid_supporting")
        self.assertEqual(missing_local.classification, "not_in_supplied_context")
        self.assertEqual(fabricated.classification, "fabricated")

    def test_explicit_alias_map_preserves_baseline_citation_behavior(self):
        resolution = resolve_citation_id(
            "C1",
            answer_citations=[],
            valid_context_ids={"source-1"},
            aliases={"C1": "source-1"},
        )

        self.assertEqual(resolution.resolved_id, "source-1")
        self.assertEqual(resolution.classification, "valid_supporting")

    def test_claim_support_uses_matched_claim_and_resolved_citation(self):
        claim = SimpleNamespace(
            claim_id="claim-1",
            claim_text="The corrected creatinine is 1.2 after repeat testing.",
            normalized_claim={},
            source_support_status="",
        )
        match = ClaimMatchResult(
            claim_id="claim-1",
            matched_truth_id="truth-1",
            matched_truth_text="Corrected creatinine is 1.2 after repeat testing.",
            score=0.94,
            correctness=True,
            reason="test_match",
        )
        citation = resolve_citation_id(
            "C1",
            answer_citations=[{"citation_id": "C1", "canonical_source_id": "source-1"}],
            valid_context_ids={"source-1"},
        )

        status, reason = classify_claim(claim, match, [citation])

        self.assertEqual(status, "supported")
        self.assertEqual(reason, "matched_expected_claim_and_has_valid_citation")

    def test_claim_without_match_or_resolved_support_remains_unsupported(self):
        claim = SimpleNamespace(
            claim_id="claim-1",
            claim_text="The patient definitely has an unsupported new diagnosis.",
            normalized_claim={},
            source_support_status="",
        )

        status, reason = classify_claim(claim, None, [])

        self.assertEqual(status, "unsupported")
        self.assertEqual(reason, "no_expected_claim_match_or_resolved_support")

    def test_temporal_and_state_transition_mapping_use_benchmark_terms(self):
        temporal_value, temporal_reason = temporal_score(
            "After the repeat lab, the latest creatinine is corrected to 1.2.",
            ["The answer should use the latest value after correction."],
        )
        state_value, state_reason = memory_update_accuracy(
            "After the repeat lab, the latest creatinine is corrected to 1.2.",
            SimpleNamespace(truth={"expected_state_transitions": ["creatinine corrected to 1.2 after repeat lab"]}),
        )

        self.assertGreater(temporal_value, 0.0)
        self.assertEqual(temporal_reason, "temporal_markers_found_in_stored_answer")
        self.assertGreater(state_value, 0.0)
        self.assertEqual(state_reason, "expected_state_transition_terms_found_in_stored_answer")

    def test_csm_v3_only_observations_export_csm_v3_activation_metrics(self):
        observations = [
            observation("SYN-CSM-002", "q1", "t1", "csm_v3", "activation_precision", 1.0),
            observation("SYN-CSM-002", "q2", "t2", "csm_v3", "activation_precision", 0.0),
            observation("SYN-CSM-002", "q1", "t1", "csm_v3", "activation_recall", 0.5),
        ]

        matrix = aggregate_observations(observations)
        precision = next(row for row in matrix if row["system"] == "csm_v3" and row["metric_name"] == "activation_precision")
        recall = next(row for row in matrix if row["system"] == "csm_v3" and row["metric_name"] == "activation_recall")

        self.assertEqual(systems_for_observations(observations), ["csm_v3"])
        self.assertEqual(precision["patient"], "SYN-CSM-002")
        self.assertEqual(precision["questions"], 2)
        self.assertEqual(precision["completed_turns"], 2)
        self.assertEqual(precision["value"], 0.5)
        self.assertEqual(recall["value"], 0.5)

    def test_baseline_only_observations_do_not_add_csm_v3(self):
        observations = [observation("SYN-CSM-001", "q1", "t1", "long_context", "answer_accuracy", 1.0)]

        self.assertEqual(systems_for_observations(observations), ["long_context"])


def observation(patient: str, question_id: str, turn_id: str, system: str, metric: str, value: float) -> dict:
    return {
        "patient": patient,
        "question_id": question_id,
        "question_number": 1,
        "turn_id": turn_id,
        "system": system,
        "metric_name": metric,
        "observation_value": value,
        "applicable": True,
        "reason_not_applicable": None,
    }
