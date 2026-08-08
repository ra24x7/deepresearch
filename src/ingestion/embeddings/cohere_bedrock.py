import json
import time
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError

from config import EmbeddingSettings
from ingestion.embeddings.exceptions import EmbeddingInvocationError

_MAX_BATCH_SIZE = 96
_INPUT_TYPE_PASSAGE = "search_document"
_INPUT_TYPE_QUERY = "search_query"
_THROTTLING_ERROR_CODE = "ThrottlingException"
# Bedrock enforces a tokens-per-minute ceiling; backoff must be able to outwait
# a full window, so the doubling sequence sums past 60s within max_retries.
_BACKOFF_BASE_SECONDS = 4.0


def _parse_embeddings(response: Any, expected: int) -> list[list[float]]:
    try:
        embeddings = json.loads(response["body"].read())["embeddings"]["float"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise EmbeddingInvocationError(f"Cohere Bedrock embed response was malformed: {exc}") from exc
    # A short vector list silently misaligns embeddings with their texts, so
    # every document after the gap would be indexed under the wrong vector.
    if len(embeddings) != expected:
        raise EmbeddingInvocationError(f"Cohere Bedrock returned {len(embeddings)} embeddings for {expected} texts")
    return embeddings


class CohereBedrockProvider:
    """Embedding provider backed by Cohere Embed v4 on Bedrock."""

    def __init__(self, client: Any, settings: EmbeddingSettings):
        self._client = client
        self._settings = settings

    @property
    def model_id(self) -> str:
        return self._settings.model_id

    @property
    def dimension(self) -> int:
        return self._settings.dimension

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for start in range(0, len(texts), _MAX_BATCH_SIZE):
            batch = texts[start : start + _MAX_BATCH_SIZE]
            embeddings.extend(self._invoke(batch, _INPUT_TYPE_PASSAGE))
        return embeddings

    def embed_query(self, text: str) -> list[float]:
        return self._invoke([text], _INPUT_TYPE_QUERY)[0]

    def _invoke(self, texts: list[str], input_type: str) -> list[list[float]]:
        payload = {
            "texts": texts,
            "input_type": input_type,
            "embedding_types": ["float"],
            "output_dimension": self._settings.dimension,
        }
        last_error: Exception | None = None
        for attempt in range(self._settings.max_retries):
            if attempt > 0:
                time.sleep(_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)))
            try:
                response = self._client.invoke_model(modelId=self._settings.model_id, body=json.dumps(payload))
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code", "") != _THROTTLING_ERROR_CODE:
                    raise EmbeddingInvocationError(f"Cohere Bedrock embed call failed: {exc}") from exc
                last_error = exc
                continue
            except BotoCoreError as exc:
                # Timeouts and connection failures are not ClientError; unwrapped
                # they reach the caller as a raw botocore error.
                raise EmbeddingInvocationError(f"Cohere Bedrock embed call failed: {exc}") from exc
            return _parse_embeddings(response, len(texts))
        raise EmbeddingInvocationError(
            f"Cohere Bedrock embed call throttled after {self._settings.max_retries} attempts: {last_error}"
        ) from last_error
