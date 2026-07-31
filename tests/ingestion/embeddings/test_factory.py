from unittest.mock import MagicMock

import pytest

from config import EmbeddingSettings
from ingestion.embeddings.cohere_bedrock import CohereBedrockProvider
from ingestion.embeddings.exceptions import MissingEmbeddingClientError, UnknownEmbeddingProviderError
from ingestion.embeddings.factory import build_provider
from ingestion.embeddings.fake import FakeEmbeddingProvider


class TestBuildProvider:
    def test_builds_fake_provider_with_configured_dimension(self):
        settings = EmbeddingSettings(provider="fake", dimension=8)

        provider = build_provider(settings)

        assert isinstance(provider, FakeEmbeddingProvider)
        assert provider.dimension == 8

    def test_builds_cohere_bedrock_provider_when_client_given(self):
        settings = EmbeddingSettings(provider="cohere_bedrock")
        client = MagicMock()

        provider = build_provider(settings, bedrock_client=client)

        assert isinstance(provider, CohereBedrockProvider)

    def test_raises_when_cohere_bedrock_requested_without_client(self):
        settings = EmbeddingSettings(provider="cohere_bedrock")

        with pytest.raises(MissingEmbeddingClientError):
            build_provider(settings)

    def test_raises_on_unknown_provider(self):
        settings = EmbeddingSettings(provider="nonexistent")

        with pytest.raises(UnknownEmbeddingProviderError):
            build_provider(settings)
