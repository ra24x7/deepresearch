import json
import time
from typing import Any, NamedTuple, Protocol

from botocore.exceptions import ClientError

from llm.exceptions import LLMInvocationError, LLMJSONParseError

_THROTTLING_ERROR_CODE = "ThrottlingException"
_BACKOFF_BASE_SECONDS = 2.0


class ConverseSettings(Protocol):
    """The four fields this module reads. Enrichment, generation and judging
    each carry their own settings class; all three satisfy this."""

    model_id: str
    max_tokens: int
    temperature: float
    max_retries: int


class Usage(NamedTuple):
    input_tokens: int
    output_tokens: int


def invoke(prompt: str, client: Any, settings: ConverseSettings) -> tuple[str, Usage]:
    response = _converse_with_retry(prompt, client, settings)
    text = response["output"]["message"]["content"][0]["text"]
    return text, _extract_usage(response)


def invoke_json(prompt: str, client: Any, settings: ConverseSettings) -> tuple[dict, Usage]:
    text, usage = invoke(prompt, client, settings)
    parsed = _try_parse_json(text)
    if parsed is not None:
        return parsed, usage

    retry_text, retry_usage = invoke(prompt, client, settings)
    combined_usage = Usage(
        input_tokens=usage.input_tokens + retry_usage.input_tokens,
        output_tokens=usage.output_tokens + retry_usage.output_tokens,
    )
    parsed = _try_parse_json(retry_text)
    if parsed is not None:
        return parsed, combined_usage

    raise LLMJSONParseError(f"Model response was not valid JSON after retry: {retry_text!r}")


def _try_parse_json(text: str) -> dict | None:
    try:
        return json.loads(_strip_markdown_fence(text))
    except json.JSONDecodeError:
        return None


def _strip_markdown_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`").removeprefix("json")
    return stripped.strip()


def _converse_with_retry(prompt: str, client: Any, settings: ConverseSettings) -> dict:
    last_error: Exception | None = None
    for attempt in range(settings.max_retries):
        if attempt > 0:
            time.sleep(_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)))
        try:
            return client.converse(
                modelId=settings.model_id,
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                inferenceConfig={"maxTokens": settings.max_tokens, "temperature": settings.temperature},
            )
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code != _THROTTLING_ERROR_CODE:
                raise LLMInvocationError(f"Bedrock converse call failed: {exc}") from exc
            last_error = exc
    raise LLMInvocationError(f"Bedrock converse call failed after {settings.max_retries} attempts: {last_error}")


def _extract_usage(response: dict) -> Usage:
    usage = response.get("usage", {})
    return Usage(input_tokens=usage.get("inputTokens", 0), output_tokens=usage.get("outputTokens", 0))
