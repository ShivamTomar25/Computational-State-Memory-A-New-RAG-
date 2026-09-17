from types import SimpleNamespace
from unittest import TestCase
from uuid import uuid4

from app.evaluation.metrics.calculators.context import EvaluationTurnContext
from app.evaluation.metrics.calculators.result_calculator import calculate_run_metrics


class EvaluationMetricCalculatorTests(TestCase):
    def test_calculates_claim_retrieval_token_latency_and_cost_metrics(self):
        context = build_context(
            generated_claims=[
                SimpleNamespace(
                    claim_id="gen-1",
                    claim_text="Type 2 diabetes is active.",
                    normalized_claim={
                        "subject": "Type 2 diabetes mellitus",
                        "predicate": "clinical_status",
                        "value": "active",
                        "status": "active",
                        "confidence": 0.9,
                    },
                    citation_ids=["event-1"],
                    source_support_status=None,
                )
            ],
            retrieval_items=[SimpleNamespace(canonical_source_id="event-1", document_id=None, section_id=None)],
            llm_call=SimpleNamespace(
                request_status="completed",
                provider="groq",
                model="openai/gpt-oss-120b",
                input_token_count=100,
                output_token_count=40,
                duration_ms=250,
            ),
            structured_answer={"decision_labels": ["current_state_active"]},
        )

        results = calculate_run_metrics([context])

        self.assertEqual(len(results), 21)
        self.assertEqual(results["answer_accuracy"].value, 1.0)
        self.assertEqual(results["hallucination_rate"].value, 0.0)
        self.assertEqual(results["evidence_support_rate"].value, 1.0)
        self.assertEqual(results["unsupported_claim_rate"].value, 0.0)
        self.assertEqual(results["fabricated_citation_rate"].value, 0.0)
        self.assertEqual(results["lineage_citation_f1"].value, 1.0)
        self.assertEqual(results["retrieval_precision"].value, 1.0)
        self.assertEqual(results["retrieval_recall"].value, 1.0)
        self.assertEqual(results["tokens_per_query"].value, 140)
        self.assertEqual(results["p95_latency"].value, 250)
        self.assertGreater(results["total_cost"].value, 0)
        self.assertEqual(results["decision_f1"].value, 1.0)

    def test_missing_complex_inputs_are_not_applicable_not_fake_zero(self):
        context = build_context(generated_claims=[], retrieval_items=[], llm_call=None, structured_answer={})

        results = calculate_run_metrics([context])

        self.assertEqual(results["answer_accuracy"].value, 0.0)
        self.assertFalse(results["retrieval_precision"].applicable)
        self.assertIsNone(results["retrieval_precision"].value)
        self.assertEqual(results["retrieval_precision"].reason_not_applicable, "no_retrieved_context_items")
        self.assertFalse(results["total_cost"].applicable)
        self.assertIsNone(results["total_cost"].value)
        self.assertFalse(results["expected_calibration_error"].applicable)
        self.assertIsNone(results["expected_calibration_error"].value)
        self.assertFalse(results["temporal_consistency"].applicable)
        self.assertIsNone(results["temporal_consistency"].value)


def build_context(generated_claims, retrieval_items, llm_call, structured_answer):
    question_id = uuid4()
    turn_id = uuid4()

    return EvaluationTurnContext(
        turn=SimpleNamespace(id=turn_id, started_at=None, completed_at=None),
        question=SimpleNamespace(id=question_id),
        ground_truth=SimpleNamespace(
            question_id=question_id,
            truth={
                "claims": [
                    {
                        "claim_id": "gt-1",
                        "subject": "Type 2 diabetes mellitus",
                        "predicate": "clinical_status",
                        "value": "active",
                        "status": "active",
                        "relevant_source_ids": ["event-1"],
                    }
                ],
                "decision_labels": ["current_state_active"],
                "relevant_source_ids": ["event-1"],
            },
        ),
        output=SimpleNamespace(
            structured_answer=structured_answer,
            citations=["event-1"] if generated_claims else [],
            conflicts=[],
        ),
        claims=generated_claims,
        retrieval_items=retrieval_items,
        llm_call=llm_call,
    )
