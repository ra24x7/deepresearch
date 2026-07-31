from typing import Any

from config import EmbeddingSettings
from ingestion.embeddings.base import EmbeddingProvider
from ingestion.embeddings.cohere_bedrock import CohereBedrockProvider
from ingestion.embeddings.exceptions import MissingEmbeddingClientError, UnknownEmbeddingProviderError
from ingestion.embeddings.fake import FakeEmbeddingProvider

_PROVIDER_COHERE_BEDROCK = "cohere_bedrock"
_PROVIDER_FAKE = "fake"


def build_provider(settings: EmbeddingSettings, bedrock_client: Any = None) -> EmbeddingProvider:
    if settings.provider == _PROVIDER_COHERE_BEDROCK:
        if bedrock_client is None:
            raise MissingEmbeddingClientError("cohere_bedrock provider requires a bedrock_client")
        return CohereBedrockProvider(bedrock_client, settings)
    if settings.provider == _PROVIDER_FAKE:
        return FakeEmbeddingProvider(settings.dimension)
    raise UnknownEmbeddingProviderError(f"Unknown embedding provider: {settings.provider!r}")
