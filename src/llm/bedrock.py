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
    # Bedrock reports cache tokens outside inputTokens, and they are billed at
    # their own rates, so they are counted separately all the way to the ledger.
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


def invoke(
    prompt: str, client: Any, settings: ConverseSettings, cached_prefix: str | None = None
) -> tuple[str, Usage]:
    """`cached_prefix` is text stable across calls -- a rubric, a system brief.

    It is sent ahead of a cache point, so Bedrock bills it once per cache
    lifetime rather than once per call. Note that it becomes its own content
    block: the model sees the same text, but not in the same single block, so a
    prompt whose grades are calibrated must be re-verified after adopting this.
    """
    response = _converse_with_retry(prompt, client, settings, cached_prefix)
    text = response["output"]["message"]["content"][0]["text"]
    return text, _extract_usage(response)


def invoke_json(
    prompt: str, client: Any, settings: ConverseSettings, cached_prefix: str | None = None
) -> tuple[dict, Usage]:
    text, usage = invoke(prompt, client, settings, cached_prefix)
    parsed = _try_parse_json(text)
    if parsed is not None:
        return parsed, usage

    retry_text, retry_usage = invoke(prompt, client, settings, cached_prefix)
    combined_usage = Usage(
        input_tokens=usage.input_tokens + retry_usage.input_tokens,
        output_tokens=usage.output_tokens + retry_usage.output_tokens,
        cache_read_tokens=usage.cache_read_tokens + retry_usage.cache_read_tokens,
        cache_write_tokens=usage.cache_write_tokens + retry_usage.cache_write_tokens,
    )
    parsed = _try_parse_json(retry_text)
    if parsed is not None:
        return parsed, combined_usage

    raise LLMJSONParseError(f"Model response was not valid JSON after retry: {retry_text!r}")


def _try_parse_json(text: str) -> dict | None:
    try:
        return json.loads(_strip_markdown_fence(text))
    except json.JSONDecodeError:
        return _extract_braced_json(text)


def _extract_braced_json(text: str) -> dict | None:
    # A model asked for JSON may still reason in prose first — the judge does
    # this on hard questions. Phase 1's notebook scanned for the outermost
    # braces; reusing invoke_json lost that tolerance and killed a 150-question
    # run at question 34.
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def _strip_markdown_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`").removeprefix("json")
    return stripped.strip()


def _content_blocks(prompt: str, cached_prefix: str | None) -> list[dict]:
    if not cached_prefix:
        return [{"text": prompt}]
    return [{"text": cached_prefix}, {"cachePoint": {"type": "default"}}, {"text": prompt}]


def _converse_with_retry(
    prompt: str, client: Any, settings: ConverseSettings, cached_prefix: str | None = None
) -> dict:
    content = _content_blocks(prompt, cached_prefix)
    last_error: Exception | None = None
    for attempt in range(settings.max_retries):
        if attempt > 0:
            time.sleep(_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)))
        try:
            return client.converse(
                modelId=settings.model_id,
                messages=[{"role": "user", "content": content}],
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
    return Usage(
        input_tokens=usage.get("inputTokens", 0),
        output_tokens=usage.get("outputTokens", 0),
        cache_read_tokens=usage.get("cacheReadInputTokens", 0),
        cache_write_tokens=usage.get("cacheWriteInputTokens", 0),
    )
