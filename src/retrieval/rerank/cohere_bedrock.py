import json
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError

from config import RerankSettings
from retrieval.rerank.exceptions import RerankInvocationError
from retrieval.schemas import FusedHit

# Cohere's rerank payload schema version, not the model version.
_API_VERSION = 2


def _parse_results(response: Any) -> list[dict]:
    try:
        return json.loads(response["body"].read())["results"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise RerankInvocationError(f"Cohere rerank response was malformed: {exc}") from exc


def _apply_results(results: list[dict], candidates: list[FusedHit]) -> list[FusedHit]:
    hits = []
    for result in results:
        index = result.get("index") if isinstance(result, dict) else None
        # Dropping an unusable entry instead would quietly shorten the shortlist
        # and look like the reranker simply preferred fewer documents. A negative
        # index is worse than out of range: Python would score the wrong hit.
        if not isinstance(index, int) or not 0 <= index < len(candidates) or "relevance_score" not in result:
            raise RerankInvocationError(
                f"Cohere rerank returned an unusable result {result!r} for {len(candidates)} candidates"
            )
        hits.append(candidates[index].model_copy(update={"score": result["relevance_score"]}))
    return hits


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
        except (BotoCoreError, ClientError) as exc:
            raise RerankInvocationError(f"Cohere rerank call failed: {exc}") from exc

        return _apply_results(_parse_results(response), candidates)
