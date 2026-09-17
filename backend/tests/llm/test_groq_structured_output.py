from __future__ import annotations

import unittest
from unittest.mock import patch

from pydantic import BaseModel, Field, RootModel

from app.config import settings
from app.llm.common.exceptions.errors import LlmStructuredOutputFailed
from app.llm.common.schemas.answer import LlmProviderRequest
from app.llm.providers.groq.provider import (
    GroqChatProvider,
    extract_json_value,
    is_truncated_response,
    response_content_to_text,
)


class SimplePayload(BaseModel):
    answer: str
    nested: dict = Field(default_factory=dict)


class ArrayPayload(RootModel[list[dict]]):
    pass


class FakeMessage:
    def __init__(self, content, finish_reason: str = "stop"):
        self.content = content
        self.response_metadata = {"finish_reason": finish_reason}


class FailingStructuredModel:
    def invoke(self, _messages):
        raise RuntimeError("native structured output failed")


class FakeRawModel:
    def __init__(self, responses):
        self.responses = list(responses)

    def with_structured_output(self, _schema, method=None):
        return FailingStructuredModel()

    def invoke(self, _messages):
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class TestableGroqProvider(GroqChatProvider):
    def __init__(self, responses):
        self.model = FakeRawModel(responses)
        self.rebuilt_token_limits = []

    def _build_model(self, *, max_tokens=None, max_retries=None):
        self.rebuilt_token_limits.append(max_tokens)
        return self.model


class GroqStructuredOutputTests(unittest.TestCase):
    def test_valid_plain_json(self):
        self.assertEqual(extract_json_value('{"answer":"ok"}'), '{"answer":"ok"}')

    def test_json_in_markdown_fence(self):
        self.assertEqual(extract_json_value('```json\n{"answer":"ok"}\n```'), '{"answer":"ok"}')

    def test_text_before_valid_json(self):
        self.assertEqual(extract_json_value('Here is it: {"answer":"ok"}'), '{"answer":"ok"}')

    def test_text_after_valid_json(self):
        self.assertEqual(extract_json_value('{"answer":"ok"} done'), '{"answer":"ok"}')

    def test_nested_objects_and_arrays(self):
        payload = '{"answer":"ok","nested":{"items":[{"a":1},{"b":2}]}}'
        self.assertEqual(extract_json_value(f"prefix {payload} suffix"), payload)

    def test_braces_inside_quoted_strings(self):
        payload = '{"answer":"value with {braces} inside"}'
        self.assertEqual(extract_json_value(payload), payload)

    def test_escaped_quotation_marks(self):
        payload = '{"answer":"the \\"quoted\\" value"}'
        self.assertEqual(extract_json_value(payload), payload)

    def test_content_block_response(self):
        content = [{"type": "text", "text": "prefix "}, {"type": "text", "text": '{"answer":"ok"}'}]
        self.assertEqual(response_content_to_text(content), 'prefix \n{"answer":"ok"}')
        self.assertEqual(extract_json_value(content), '{"answer":"ok"}')

    def test_array_json(self):
        self.assertEqual(extract_json_value('before [{"a":1}] after'), '[{"a":1}]')

    def test_truncated_json(self):
        content = '{"answer":"unfinished"'
        self.assertTrue(is_truncated_response(content, "length"))
        with self.assertRaises(ValueError):
            extract_json_value(content)

    def test_completely_non_json_output(self):
        with self.assertRaises(ValueError):
            extract_json_value("not json")

    def test_schema_invalid_but_syntactically_valid_json(self):
        provider = TestableGroqProvider([FakeMessage('{"nested":{}}')])
        with patch.object(settings, "groq_api_key", "gsk_test"):
            with self.assertRaises(LlmStructuredOutputFailed):
                provider.invoke_structured(
                    LlmProviderRequest(
                        task_type="unit",
                        system_prompt="system",
                        user_prompt="user",
                        model_configuration={"max_retries": 1, "request_delay_seconds": 0},
                    ),
                    SimplePayload,
                )

    def test_successful_corrective_retry(self):
        provider = TestableGroqProvider(
            [
                FakeMessage('{"answer":"unfinished"', finish_reason="length"),
                FakeMessage('{"answer":"ok","nested":{"x":1}}'),
            ]
        )
        with patch.object(settings, "groq_api_key", "gsk_test"):
            result = provider.invoke_structured(
                LlmProviderRequest(
                    task_type="unit",
                    system_prompt="system",
                    user_prompt="user",
                    model_configuration={"max_retries": 2, "request_delay_seconds": 0},
                ),
                SimplePayload,
            )

        self.assertEqual(result.structured_value.answer, "ok")
        self.assertEqual(result.retry_count, 2)
        attempts = result.metadata["structured_output_attempts"]
        self.assertEqual(attempts[-1]["outcome"], "succeeded")
        self.assertTrue(attempts[-1]["corrective_retry_required"])
        self.assertIn(4096, provider.rebuilt_token_limits)

    def test_exhausted_retries_records_attempts_for_pending_retry(self):
        provider = TestableGroqProvider([FakeMessage("not json"), FakeMessage("still not json")])
        with patch.object(settings, "groq_api_key", "gsk_test"):
            with self.assertRaises(LlmStructuredOutputFailed) as captured:
                provider.invoke_structured(
                    LlmProviderRequest(
                        task_type="unit",
                        system_prompt="system",
                        user_prompt="user",
                        model_configuration={"max_retries": 2, "request_delay_seconds": 0},
                    ),
                    SimplePayload,
                )

        attempts = captured.exception.structured_output_attempts
        self.assertEqual([attempt["outcome"] for attempt in attempts], ["failed", "failed"])
        self.assertIn("No JSON object", attempts[0]["validation_error"])

    def test_root_array_schema_can_validate_extracted_array(self):
        provider = TestableGroqProvider([FakeMessage('prefix [{"a":1}] suffix')])
        with patch.object(settings, "groq_api_key", "gsk_test"):
            result = provider.invoke_structured(
                LlmProviderRequest(
                    task_type="unit",
                    system_prompt="system",
                    user_prompt="user",
                    model_configuration={"max_retries": 1, "request_delay_seconds": 0},
                ),
                ArrayPayload,
            )

        self.assertEqual(result.structured_value.root, [{"a": 1}])


if __name__ == "__main__":
    unittest.main()
