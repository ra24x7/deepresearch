from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from config import EnrichmentSettings
from llm.bedrock import Usage, invoke, invoke_json
from llm.exceptions import LLMInvocationError, LLMJSONParseError

SETTINGS = EnrichmentSettings(
    model_id="global.anthropic.claude-haiku-4-5-20251001-v1:0",
    max_tokens=1024,
    temperature=0.0,
    timeout_seconds=10.0,
    max_retries=3,
)


def _converse_response(text: str, input_tokens: int = 10, output_tokens: int = 5) -> dict:
    return {
        "output": {"message": {"content": [{"text": text}]}},
        "usage": {"inputTokens": input_tokens, "outputTokens": output_tokens},
    }


def _client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "boom"}}, "Converse")


class TestInvoke:
    def test_returns_text_and_usage_from_converse_response(self):
        client = MagicMock()
        client.converse.return_value = _converse_response("hello world", 12, 34)

        text, usage = invoke("prompt", client, SETTINGS)

        assert text == "hello world"
        assert usage == Usage(input_tokens=12, output_tokens=34)

    def test_sends_model_id_max_tokens_and_temperature_from_settings(self):
        client = MagicMock()
        client.converse.return_value = _converse_response("ok")

        invoke("my prompt", client, SETTINGS)

        _, kwargs = client.converse.call_args
        assert kwargs["modelId"] == SETTINGS.model_id
        assert kwargs["inferenceConfig"]["maxTokens"] == SETTINGS.max_tokens
        assert kwargs["inferenceConfig"]["temperature"] == SETTINGS.temperature
        assert kwargs["messages"][0]["content"][0]["text"] == "my prompt"

    def test_retries_on_throttling_exception_then_succeeds(self, mocker):
        mocker.patch("llm.bedrock.time.sleep")
        client = MagicMock()
        client.converse.side_effect = [_client_error("ThrottlingException"), _converse_response("recovered")]

        text, _ = invoke("prompt", client, SETTINGS)

        assert text == "recovered"
        assert client.converse.call_count == 2

    def test_raises_typed_error_after_max_retries_exhausted_on_throttling(self, mocker):
        mocker.patch("llm.bedrock.time.sleep")
        client = MagicMock()
        client.converse.side_effect = [_client_error("ThrottlingException")] * SETTINGS.max_retries

        with pytest.raises(LLMInvocationError):
            invoke("prompt", client, SETTINGS)

        assert client.converse.call_count == SETTINGS.max_retries

    def test_raises_typed_error_immediately_on_non_throttling_client_error(self, mocker):
        mocker.patch("llm.bedrock.time.sleep")
        client = MagicMock()
        client.converse.side_effect = _client_error("ValidationException")

        with pytest.raises(LLMInvocationError):
            invoke("prompt", client, SETTINGS)

        assert client.converse.call_count == 1


class TestInvokeJson:
    def test_parses_valid_json_response(self):
        client = MagicMock()
        client.converse.return_value = _converse_response('{"claims": []}')

        data, usage = invoke_json("prompt", client, SETTINGS)

        assert data == {"claims": []}
        assert usage == Usage(input_tokens=10, output_tokens=5)
        assert client.converse.call_count == 1

    def test_strips_markdown_json_fence_before_parsing(self):
        client = MagicMock()
        client.converse.return_value = _converse_response('```json\n{"a": 1}\n```')

        data, _ = invoke_json("prompt", client, SETTINGS)

        assert data == {"a": 1}

    def test_extracts_json_that_follows_a_prose_preamble(self):
        # the judge reasons in prose before answering on hard questions; Phase 1
        # tolerated this by scanning for the outermost braces, and a full
        # 150-question run died at question 34 when that tolerance was lost
        client = MagicMock()
        client.converse.return_value = _converse_response(
            'Looking at the candidate answer, I need to check both claims.\n\n'
            '{"verdict": "WRONG", "reason": "Rule 3: incomplete."}'
        )

        data, _ = invoke_json("prompt", client, SETTINGS)

        assert data == {"verdict": "WRONG", "reason": "Rule 3: incomplete."}
        assert client.converse.call_count == 1

    def test_extracts_json_wrapped_in_prose_on_both_sides(self):
        client = MagicMock()
        client.converse.return_value = _converse_response(
            'Here is my assessment.\n{"a": 1}\nLet me know if you need more.'
        )

        data, _ = invoke_json("prompt", client, SETTINGS)

        assert data == {"a": 1}

    def test_prose_with_no_json_at_all_still_raises(self):
        client = MagicMock()
        client.converse.return_value = _converse_response("I cannot grade this answer.")

        with pytest.raises(LLMJSONParseError):
            invoke_json("prompt", client, SETTINGS)

    def test_retries_same_prompt_once_on_malformed_json_then_succeeds(self):
        client = MagicMock()
        client.converse.side_effect = [
            _converse_response("not json", 10, 5),
            _converse_response('{"ok": true}', 8, 3),
        ]

        data, usage = invoke_json("prompt", client, SETTINGS)

        assert data == {"ok": True}
        assert client.converse.call_count == 2
        assert usage == Usage(input_tokens=18, output_tokens=8)

    def test_raises_typed_error_when_retry_also_produces_malformed_json(self):
        client = MagicMock()
        client.converse.return_value = _converse_response("still not json")

        with pytest.raises(LLMJSONParseError):
            invoke_json("prompt", client, SETTINGS)

        assert client.converse.call_count == 2


class TestPromptCaching:
    """A stable prefix sent ahead of a cache point is billed once per cache
    lifetime instead of once per call. The judge re-sends one rubric on every
    question, which is what this exists for (eval-log A2).
    """

    def test_without_a_cached_prefix_the_prompt_is_a_single_block(self):
        client = MagicMock()
        client.converse.return_value = _converse_response("ok")

        invoke("just the prompt", client, SETTINGS)

        _, kwargs = client.converse.call_args
        assert kwargs["messages"][0]["content"] == [{"text": "just the prompt"}]

    def test_a_cached_prefix_is_sent_ahead_of_a_cache_point(self):
        client = MagicMock()
        client.converse.return_value = _converse_response("ok")

        invoke("the variable part", client, SETTINGS, cached_prefix="the stable rubric")

        _, kwargs = client.converse.call_args
        assert kwargs["messages"][0]["content"] == [
            {"text": "the stable rubric"},
            {"cachePoint": {"type": "default"}},
            {"text": "the variable part"},
        ]

    def test_an_empty_cached_prefix_adds_no_cache_point(self):
        client = MagicMock()
        client.converse.return_value = _converse_response("ok")

        invoke("just the prompt", client, SETTINGS, cached_prefix="")

        _, kwargs = client.converse.call_args
        assert kwargs["messages"][0]["content"] == [{"text": "just the prompt"}]

    def test_cache_token_counts_are_read_off_the_response(self):
        client = MagicMock()
        response = _converse_response("ok")
        response["usage"]["cacheReadInputTokens"] = 1_500
        response["usage"]["cacheWriteInputTokens"] = 20
        client.converse.return_value = response

        _, usage = invoke("p", client, SETTINGS)

        assert (usage.cache_read_tokens, usage.cache_write_tokens) == (1_500, 20)

    def test_a_response_without_cache_counts_reports_zero(self):
        client = MagicMock()
        client.converse.return_value = _converse_response("ok")

        _, usage = invoke("p", client, SETTINGS)

        assert (usage.cache_read_tokens, usage.cache_write_tokens) == (0, 0)

    def test_invoke_json_forwards_the_cached_prefix(self):
        client = MagicMock()
        client.converse.return_value = _converse_response('{"verdict": "CORRECT"}')

        invoke_json("the variable part", client, SETTINGS, cached_prefix="the stable rubric")

        _, kwargs = client.converse.call_args
        assert kwargs["messages"][0]["content"][0] == {"text": "the stable rubric"}
