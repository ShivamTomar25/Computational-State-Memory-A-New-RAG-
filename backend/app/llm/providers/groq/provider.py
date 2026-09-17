from __future__ import annotations

import json
import random
import re
import time

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, SecretStr

from app.config import settings
from app.llm.common.exceptions.errors import LlmNotConfigured, LlmProviderUnavailable, LlmStructuredOutputFailed
from app.llm.common.schemas.answer import LlmProviderRequest, LlmProviderResult
from app.llm.common.token_budget.counter import estimate_llm_tokens


class GroqChatProvider:
    supports_structured_output = True
    supports_streaming = True

    def invoke_structured(
        self,
        request: LlmProviderRequest,
        response_schema: type[BaseModel],
    ) -> LlmProviderResult:
        if not settings.groq_api_key:
            raise LlmNotConfigured("GROQ_API_KEY is not configured.")

        started = time.monotonic()
        max_retries = int(request.model_configuration.get("max_retries", settings.groq_max_retries))
        request_delay = float(request.model_configuration.get("request_delay_seconds", 0) or 0)
        structured_method = request.model_configuration.get("structured_method") or self._structured_method_for_task(request.task_type)
        model = self._build_model(
            max_tokens=self._max_tokens_for_task(request.task_type),
            max_retries=0 if max_retries else settings.groq_max_retries,
        )
        structured_model = model.with_structured_output(response_schema, method=structured_method)
        attempts = []
        json_instruction = (
            "\n\nReturn only one complete JSON object matching the requested schema. "
            "Do not include Markdown, commentary, reasoning, or code fences."
        )

        try:
            value = self._invoke_with_backoff(
                lambda: structured_model.invoke(
                    [
                        SystemMessage(content=f"{request.system_prompt}{json_instruction}"),
                        HumanMessage(content=request.user_prompt),
                    ]
                ),
                max_retries=max_retries,
                request_delay=request_delay,
            )
            attempts.append(
                structured_attempt_record(
                    attempt_number=0,
                    stage="native_structured_output",
                    outcome="succeeded",
                    finish_reason="stop",
                    deterministic_extraction_succeeded=False,
                    corrective_retry_required=False,
                )
            )
        except Exception as error:
            if is_rate_limit_error(error) or is_rate_limit_unavailable(error):
                raise LlmProviderUnavailable("Groq rate limit exceeded.") from error

            attempts.append(
                structured_attempt_record(
                    attempt_number=0,
                    stage="native_structured_output",
                    outcome="failed",
                    validation_error=f"{error.__class__.__name__}: {str(error)[:300]}",
                    deterministic_extraction_succeeded=False,
                    corrective_retry_required=False,
                )
            )
            value, fallback_content, fallback_tokens, fallback_attempts = self._invoke_raw_json_fallback(
                model=model,
                request=request,
                response_schema=response_schema,
                max_retries=max_retries,
                request_delay=request_delay,
            )
            attempts.extend(fallback_attempts)
            content = value.model_dump_json()
            input_text = f"{request.system_prompt}\n{request.user_prompt}"
            input_tokens = estimate_llm_tokens(input_text) + fallback_tokens["input"]
            output_tokens = estimate_llm_tokens(content) + fallback_tokens["output"]

            return LlmProviderResult(
                content=fallback_content or content,
                structured_value=value,
                provider="groq",
                model=settings.groq_model,
                prompt_version=settings.llm_prompt_version,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                duration_ms=int((time.monotonic() - started) * 1000),
                finish_reason="stop",
                retry_count=sum(1 for attempt in attempts if attempt["attempt_number"] > 0),
                warnings=["Structured tool output failed; parsed validated raw JSON fallback."],
                metadata={"structured_output_attempts": attempts},
            )

        if not isinstance(value, response_schema):
            try:
                value = response_schema.model_validate(value)
            except Exception as error:
                raise LlmStructuredOutputFailed("Groq structured output did not match the expected schema.") from error

        content = value.model_dump_json()
        input_text = f"{request.system_prompt}\n{request.user_prompt}"
        input_tokens = estimate_llm_tokens(input_text)
        output_tokens = estimate_llm_tokens(content)

        return LlmProviderResult(
            content=content,
            structured_value=value,
            provider="groq",
            model=settings.groq_model,
            prompt_version=settings.llm_prompt_version,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            duration_ms=int((time.monotonic() - started) * 1000),
            finish_reason="stop",
            retry_count=0,
            metadata={"structured_output_attempts": attempts},
        )

    def health(self) -> str:
        if settings.llm_provider != "groq":
            return "disabled"

        if not settings.groq_api_key:
            return "not_configured"

        try:
            self._build_model()
        except Exception:
            return "unavailable"

        return "configured"

    def model_metadata(self) -> dict:
        return {
            "provider": "groq",
            "model": settings.groq_model,
            "fallback_model": settings.groq_fallback_model,
            "fallback_allowed": settings.groq_allow_fallback,
            "experiment_mode": settings.llm_experiment_mode,
            "configured": bool(settings.groq_api_key),
        }

    def count_tokens(self, text: str) -> int:
        return estimate_llm_tokens(text)

    def _max_tokens_for_task(self, task_type: str) -> int:
        if task_type == "rolling_summary":
            return settings.groq_summary_max_tokens

        if task_type in {"graph_extraction", "graphrag_extraction"}:
            return settings.groq_graph_max_tokens

        if task_type in {"extraction", "document_extraction"}:
            return settings.groq_extraction_max_tokens

        return settings.groq_answer_max_tokens

    def _structured_method_for_task(self, task_type: str) -> str:
        return "function_calling"

    def _build_model(self, *, max_tokens: int | None = None, max_retries: int | None = None):
        try:
            from langchain_groq import ChatGroq
        except Exception as error:
            raise LlmProviderUnavailable("langchain-groq is not installed.") from error

        return ChatGroq(
            model=settings.groq_model,
            api_key=SecretStr(settings.groq_api_key),
            temperature=settings.groq_temperature,
            max_tokens=max_tokens or settings.groq_answer_max_tokens,
            timeout=settings.groq_timeout_seconds,
            max_retries=settings.groq_max_retries if max_retries is None else max_retries,
            reasoning_format="hidden",
        )

    def _invoke_raw_json_fallback(
        self,
        *,
        model,
        request: LlmProviderRequest,
        response_schema: type[BaseModel],
        max_retries: int,
        request_delay: float,
    ):
        schema = fallback_schema_instruction(response_schema)
        base_prompt = (
            f"{request.user_prompt}\n\n"
            "Return only valid JSON. Do not include markdown, prose, or tool-call syntax. "
            "The JSON must validate against this schema:\n"
            f"{schema}"
        )
        attempts = []
        total_input_tokens = 0
        total_output_tokens = 0
        last_error: Exception | None = None

        for attempt_number in range(1, max(1, max_retries) + 1):
            corrective_retry = attempt_number > 1
            prompt = base_prompt

            if corrective_retry:
                prompt = (
                    f"{base_prompt}\n\n"
                    "Your previous response did not contain a complete valid JSON object. "
                    "Return only one complete JSON object matching the provided schema. "
                    "Do not include Markdown, commentary, reasoning, or code fences."
                )

            max_tokens = self._max_tokens_for_task(request.task_type)

            if is_truncation_error(last_error):
                max_tokens = max(max_tokens * 2, 4096)
                retry_model = self._build_model(max_tokens=max_tokens, max_retries=0)
            else:
                retry_model = model

            started = time.monotonic()
            content = ""
            finish_reason = None
            validation_error = None
            parsed_json = None
            extraction_succeeded = False

            try:
                message = self._invoke_with_backoff(
                    lambda: retry_model.invoke(
                        [
                            SystemMessage(content=request.system_prompt),
                            HumanMessage(content=prompt),
                        ]
                    ),
                    max_retries=max_retries,
                    request_delay=request_delay,
                )
                content = response_content_to_text(getattr(message, "content", ""))
                finish_reason = response_finish_reason(message)
                total_input_tokens += estimate_llm_tokens(f"{request.system_prompt}\n{prompt}")
                total_output_tokens += estimate_llm_tokens(content)
                json_text = extract_json_value(content)
                parsed_json = json.loads(json_text)
                value = response_schema.model_validate(parsed_json)
                extraction_succeeded = True
                attempts.append(
                    structured_attempt_record(
                        attempt_number=attempt_number,
                        stage="raw_json_fallback",
                        outcome="succeeded",
                        raw_response=content,
                        parsed_json=parsed_json,
                        finish_reason=finish_reason,
                        input_tokens=estimate_llm_tokens(f"{request.system_prompt}\n{prompt}"),
                        output_tokens=estimate_llm_tokens(content),
                        latency_ms=int((time.monotonic() - started) * 1000),
                        deterministic_extraction_succeeded=True,
                        corrective_retry_required=corrective_retry,
                        truncation_detected=is_truncated_response(content, finish_reason),
                    )
                )
                return value, content, {"input": total_input_tokens, "output": total_output_tokens}, attempts
            except Exception as error:
                last_error = error

                if is_rate_limit_error(error) or is_rate_limit_unavailable(error):
                    raise LlmProviderUnavailable("Groq rate limit exceeded.") from error

                validation_error = f"{error.__class__.__name__}: {str(error)[:500]}"
                attempts.append(
                    structured_attempt_record(
                        attempt_number=attempt_number,
                        stage="raw_json_fallback",
                        outcome="failed",
                        raw_response=content,
                        parsed_json=parsed_json,
                        validation_error=validation_error,
                        finish_reason=finish_reason,
                        input_tokens=estimate_llm_tokens(f"{request.system_prompt}\n{prompt}"),
                        output_tokens=estimate_llm_tokens(content),
                        latency_ms=int((time.monotonic() - started) * 1000),
                        deterministic_extraction_succeeded=extraction_succeeded,
                        corrective_retry_required=corrective_retry,
                        truncation_detected=is_truncated_response(content, finish_reason) or is_truncation_error(error),
                    )
                )

        failure = LlmStructuredOutputFailed(
            f"Groq structured output failed: {last_error.__class__.__name__}: {str(last_error)[:240]}"
        )
        failure.structured_output_attempts = attempts
        raise failure

    def _invoke_with_backoff(self, operation, *, max_retries: int, request_delay: float):
        attempt = 0

        while True:
            if request_delay > 0:
                time.sleep(request_delay)

            try:
                return operation()
            except Exception as error:
                if not is_rate_limit_error(error):
                    raise

                if is_quota_exhausted(error):
                    raise LlmProviderUnavailable("Groq quota exhausted.") from error

                retry_after = retry_after_seconds(error)

                if attempt >= max_retries:
                    raise LlmProviderUnavailable("Groq rate limit exceeded.") from error

                base = retry_after if retry_after is not None else min(120.0, max(1.0, request_delay) * (2 ** attempt))
                time.sleep(base + random.uniform(0, min(1.0, base * 0.1)))
                attempt += 1


def response_content_to_text(content) -> str:
    if content is None:
        return ""

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                value = block.get("text") or block.get("content") or block.get("value")
                if isinstance(value, str):
                    parts.append(value)
            else:
                value = getattr(block, "text", None) or getattr(block, "content", None)
                if isinstance(value, str):
                    parts.append(value)
        return "\n".join(parts)

    return str(content)


def response_finish_reason(message) -> str | None:
    direct = getattr(message, "finish_reason", None)
    if direct:
        return str(direct)

    metadata = getattr(message, "response_metadata", None) or {}
    if isinstance(metadata, dict):
        finish_reason = metadata.get("finish_reason") or metadata.get("stop_reason")
        if finish_reason:
            return str(finish_reason)

    generation_info = getattr(message, "generation_info", None) or {}
    if isinstance(generation_info, dict):
        finish_reason = generation_info.get("finish_reason")
        if finish_reason:
            return str(finish_reason)

    return None


def extract_json_value(content) -> str:
    stripped = strip_markdown_fence(response_content_to_text(content)).strip()

    if not stripped:
        raise ValueError("No JSON content found in model output.")

    starts = [index for index, char in enumerate(stripped) if char in "{["]

    for start in starts:
        candidate = balanced_json_slice(stripped, start)
        if candidate is None:
            continue
        return candidate

    if starts:
        raise ValueError("No complete JSON object found in model output.")

    raise ValueError("No JSON object found in model output.")


def extract_json_object(content: str) -> str:
    value = extract_json_value(content)
    if not value.lstrip().startswith("{"):
        raise ValueError("JSON value is not an object.")
    return value


def strip_markdown_fence(text: str) -> str:
    stripped = text.strip()

    if not stripped.startswith("```"):
        return stripped

    first_newline = stripped.find("\n")
    last_fence = stripped.rfind("```")

    if first_newline == -1 or last_fence <= first_newline:
        return stripped.strip("`").strip()

    return stripped[first_newline + 1 : last_fence].strip()


def balanced_json_slice(text: str, start: int) -> str | None:
    opener = text[start]
    closer = "}" if opener == "{" else "]"
    matching = {"{": "}", "[": "]"}
    stack = [closer]
    in_string = False
    escape = False

    for index in range(start + 1, len(text)):
        char = text[index]

        if escape:
            escape = False
            continue

        if char == "\\":
            escape = True
            continue

        if char == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if char in matching:
            stack.append(matching[char])
            continue

        if stack and char == stack[-1]:
            stack.pop()

            if not stack:
                return text[start : index + 1]

    return None


def is_truncated_response(content: str, finish_reason: str | None = None) -> bool:
    if finish_reason and str(finish_reason).lower() in {"length", "max_tokens", "max_completion_tokens"}:
        return True

    text = response_content_to_text(content).strip()

    if not text:
        return False

    starts = [index for index, char in enumerate(text) if char in "{["]
    return bool(starts) and all(balanced_json_slice(text, start) is None for start in starts)


def is_truncation_error(error: Exception | None) -> bool:
    if error is None:
        return False

    text = str(error).lower()
    return (
        "no complete json object" in text
        or "unterminated string" in text
        or "expecting ',' delimiter" in text
        or "expecting value" in text
    )


def structured_attempt_record(
    *,
    attempt_number: int,
    stage: str,
    outcome: str,
    raw_response: str | None = None,
    parsed_json=None,
    validation_error: str | None = None,
    finish_reason: str | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    latency_ms: int = 0,
    deterministic_extraction_succeeded: bool = False,
    corrective_retry_required: bool = False,
    truncation_detected: bool = False,
) -> dict:
    record = {
        "attempt_number": attempt_number,
        "stage": stage,
        "outcome": outcome,
        "finish_reason": finish_reason,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_ms": latency_ms,
        "deterministic_extraction_succeeded": deterministic_extraction_succeeded,
        "corrective_retry_required": corrective_retry_required,
        "truncation_detected": truncation_detected,
    }

    if raw_response is not None:
        record["raw_response"] = raw_response[:8000]

    if parsed_json is not None:
        record["parsed_json"] = parsed_json

    if validation_error:
        record["validation_error"] = validation_error[:1000]

    return record


def fallback_schema_instruction(response_schema: type[BaseModel]) -> str:
    if response_schema.__name__ == "GroundedAnswer":
        return (
            "{"
            '"answer":"string",'
            '"atomic_claims":[{"claim_id":"claim-1","claim_text":"string","subject":null,'
            '"predicate":null,"value":null,"normalized_value":null,"unit":null,"status":null,'
            '"negation":false,"valid_time":null,"confidence":0.0,"uncertainty":"low",'
            '"citation_ids":["C1"]}],'
            '"citations":[{"citation_id":"C1","claim_ids":["claim-1"]}],'
            '"insufficient_evidence":false,'
            '"uncertainty":"low",'
            '"confidence":0.0,'
            '"conflicts":[],'
            '"safety_note":null,'
            '"follow_up_suggestions":[]'
            "}"
            "\nUse only citation IDs present in the supplied context, such as C1, C2, C3. "
            "If evidence is insufficient, set insufficient_evidence true, uncertainty high, and keep unsupported claims empty."
        )

    return json.dumps(response_schema.model_json_schema(), separators=(",", ":"), default=str)


def is_rate_limit_error(error: Exception) -> bool:
    if getattr(error, "status_code", None) == 429:
        return True

    response = getattr(error, "response", None)

    if getattr(response, "status_code", None) == 429:
        return True

    return error.__class__.__name__ in {"RateLimitError"}


def is_rate_limit_unavailable(error: Exception) -> bool:
    text = str(error).lower()
    return isinstance(error, LlmProviderUnavailable) and (
        "rate limit" in text or "quota" in text or "exhaust" in text
    )


def retry_after_seconds(error: Exception) -> float | None:
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", {}) or {}
    value = headers.get("retry-after") or headers.get("Retry-After")

    if not value:
        return None

    try:
        return max(0.0, float(value))
    except ValueError:
        pass

    text = str(error).lower()
    match = re.search(r"try again in\s+((?P<minutes>[0-9.]+)m)?(?P<seconds>[0-9.]+)s", text)

    if match:
        minutes = float(match.group("minutes") or 0)
        seconds = float(match.group("seconds") or 0)
        return minutes * 60 + seconds

    return None


def is_quota_exhausted(error: Exception) -> bool:
    text = str(error).lower()
    return "tokens per day" in text or " tpd" in text or "quota" in text
