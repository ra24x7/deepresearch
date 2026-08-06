import json
from typing import Any

from botocore.exceptions import ClientError

from config import RerankSettings
from retrieval.rerank.exceptions import RerankInvocationError
from retrieval.schemas import FusedHit

# Cohere's rerank payload schema version, not the model version.
_API_VERSION = 2


def _as_document(hit: FusedHit) -> str:
    # The heading often carries terms the body omits — withholding it costs the
    # reranker the strongest anchor a chunk has.
    return f"{hit.section_title}\n{hit.text}" if hit.section_title else hit.text


class CohereBedrockReranker:
    """Cohere Rerank on Bedrock. Runs in its own region — rerank is not offered
    everywhere the chat and embedding models are."""

    def __init__(self, client: Any, settings: RerankSettings):
        self._client = client
        self._settings = settings

    @property
    def model_id(self) -> str:
        return self._settings.model_id

    def rerank(self, query: str, hits: list[FusedHit], top_n: int) -> list[FusedHit]:
        if not hits:
            return []

        candidates = hits[: self._settings.max_documents]
        payload = {
            "query": query,
            "documents": [_as_document(h) for h in candidates],
            "top_n": min(top_n, len(candidates)),
            "api_version": _API_VERSION,
        }
        try:
            response = self._client.invoke_model(modelId=self._settings.model_id, body=json.dumps(payload))
        except ClientError as exc:
            raise RerankInvocationError(f"Cohere rerank call failed: {exc}") from exc

        results = json.loads(response["body"].read())["results"]
        return [
            candidates[r["index"]].model_copy(update={"score": r["relevance_score"]})
            for r in results
            if r["index"] < len(candidates)
        ]
