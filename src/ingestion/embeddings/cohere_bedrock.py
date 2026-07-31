import json
from typing import Any

from botocore.exceptions import ClientError

from config import EmbeddingSettings
from ingestion.embeddings.exceptions import EmbeddingInvocationError

_MAX_BATCH_SIZE = 96
_INPUT_TYPE_PASSAGE = "search_document"
_INPUT_TYPE_QUERY = "search_query"


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
        try:
            response = self._client.invoke_model(modelId=self._settings.model_id, body=json.dumps(payload))
        except ClientError as exc:
            raise EmbeddingInvocationError(f"Cohere Bedrock embed call failed: {exc}") from exc
        body = json.loads(response["body"].read())
        return body["embeddings"]["float"]
