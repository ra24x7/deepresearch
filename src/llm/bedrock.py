import json
import time
from typing import Any, NamedTuple

from botocore.exceptions import BotoCoreError, ClientError

from config import EnrichmentSettings
from llm.exceptions import LLMInvocationError, LLMJSONParseError

_THROTTLING_ERROR_CODE = "ThrottlingException"
_BACKOFF_BASE_SECONDS = 2.0


class Usage(NamedTuple):
    input_tokens: int
    output_tokens: int


def invoke(prompt: str, client: Any, settings: EnrichmentSettings) -> tuple[str, Usage]:
    response = _converse_with_retry(prompt, client, settings)
    try:
        text = response["output"]["message"]["content"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMInvocationError(f"Bedrock converse response had no text content: {response!r}") from exc
    return text, _extract_usage(response)


def invoke_json(prompt: str, client: Any, settings: EnrichmentSettings) -> tuple[dict, Usage]:
    text, usage = invoke(prompt, client, settings)
    parsed = _try_parse_json(text)
    if parsed is not None:
        return parsed, usage

    retry_text, retry_usage = invoke(prompt, client, settings)
    combined_usage = Usage(
        input_tokens=usage.input_tokens + retry_usage.input_tokens,
        output_tokens=usage.output_tokens + retry_usage.output_tokens,
    )
    try:
        return json.loads(_strip_markdown_fence(retry_text)), combined_usage
    except json.JSONDecodeError as exc:
        # Both responses go in the message: the first one is otherwise lost, and
        # a model that fails twice usually fails the same way twice.
        raise LLMJSONParseError(
            f"Model response was not valid JSON after retry. First: {text!r}. Retry: {retry_text!r}"
        ) from exc


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


def _converse_with_retry(prompt: str, client: Any, settings: EnrichmentSettings) -> dict:
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
        except BotoCoreError as exc:
            # Timeouts and connection failures are not ClientError; without this
            # they surface as a raw botocore error from deep inside the stack.
            raise LLMInvocationError(f"Bedrock converse call failed: {exc}") from exc
    raise LLMInvocationError(
        f"Bedrock converse call failed after {settings.max_retries} attempts: {last_error}"
    ) from last_error


def _extract_usage(response: dict) -> Usage:
    usage = response.get("usage", {})
    return Usage(input_tokens=usage.get("inputTokens", 0), output_tokens=usage.get("outputTokens", 0))
