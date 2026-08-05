from typing import Any

from config import RerankSettings
from retrieval.rerank.base import Reranker
from retrieval.rerank.cohere_bedrock import CohereBedrockReranker
from retrieval.rerank.exceptions import MissingRerankClientError, UnknownRerankerError
from retrieval.rerank.identity import IdentityReranker


def build_reranker(settings: RerankSettings, client: Any = None) -> Reranker:
    if settings.provider == "identity":
        return IdentityReranker()
    if settings.provider == "cohere_bedrock":
        if client is None:
            raise MissingRerankClientError("cohere_bedrock reranker needs a bedrock-runtime client")
        return CohereBedrockReranker(client, settings)
    raise UnknownRerankerError(f"unknown reranker provider: {settings.provider}")
