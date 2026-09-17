from __future__ import annotations

import unittest
from unittest.mock import patch

from app.config import settings
from app.llm.common.configuration.status import get_sanitized_llm_status
from app.llm.common.safety.data_egress import sanitize_for_external_llm
from app.llm.common.safety.redaction import redact_secrets
from app.llm.common.schemas.answer import GroundedAnswer, LlmContextBlock, LlmProviderRequest
from app.llm.common.structured_output.citations import validate_answer_citations
from app.llm.providers.fake.provider import DeterministicFakeChatProvider
from app.llm.providers.groq.provider import GroqChatProvider


class LlmSecurityAndProviderTests(unittest.TestCase):
    def test_groq_provider_reports_not_configured_without_key(self):
        provider = GroqChatProvider()

        with patch.object(settings, "groq_api_key", None):
            self.assertEqual(provider.health(), "not_configured")

    def test_sanitized_status_never_contains_secret_value(self):
        status = get_sanitized_llm_status().model_dump_json()

        self.assertNotIn("gsk_", status)
        self.assertIn("api_key_configured", status)

    def test_secret_redaction_removes_groq_like_keys(self):
        redacted = redact_secrets("token gsk_example_secret_value")

        self.assertEqual(redacted, "token [REDACTED]")

    def test_deidentification_removes_direct_identifiers_and_preserves_dates(self):
        patient = type(
            "Patient",
            (),
            {
                "full_name": "Asha Mehta",
                "email": "asha@example.com",
                "phone": "+91 98765 43210",
                "address": "12 Main Road",
            },
        )()
        context = [
            LlmContextBlock(
                citation_id="C1",
                source_type="patient_information",
                content="Asha Mehta had a visit on 2024-01-10. Call +91 98765 43210.",
            )
        ]

        question, clean_context, history, metadata = sanitize_for_external_llm(
            question="What happened to Asha Mehta on 2024-01-10?",
            context=context,
            history=[{"role": "user", "content": "Email asha@example.com"}],
            patient=patient,
        )

        self.assertIn("[PATIENT_NAME]", question)
        self.assertIn("2024-01-10", question)
        self.assertIn("[PATIENT_PHONE]", clean_context[0].content)
        self.assertIn("[PATIENT_EMAIL]", history[0]["content"])
        self.assertTrue(metadata["deidentified"])

    def test_fake_provider_returns_valid_structured_answer(self):
        provider = DeterministicFakeChatProvider()
        result = provider.invoke_structured(
            LlmProviderRequest(
                task_type="final_answer",
                system_prompt="system",
                user_prompt="user",
                context=[LlmContextBlock(citation_id="C1", content="Context")],
            ),
            GroundedAnswer,
        )

        self.assertIsInstance(result.structured_value, GroundedAnswer)
        self.assertEqual(result.structured_value.citations[0].citation_id, "C1")

    def test_fabricated_citations_are_removed(self):
        answer = GroundedAnswer(
            answer="Result",
            citations=[{"citation_id": "C1"}, {"citation_id": "C9"}],
            insufficient_evidence=False,
            uncertainty="low",
        )
        result = validate_answer_citations(
            answer,
            [LlmContextBlock(citation_id="C1", content="Allowed")],
        )

        self.assertEqual([citation.citation_id for citation in result.answer.citations], ["C1"])
        self.assertEqual(result.invalid_citation_ids, ["C9"])


if __name__ == "__main__":
    unittest.main()
