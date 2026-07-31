from unittest.mock import MagicMock

import pytest

from config import EmbeddingSettings
from ingestion.embeddings.base import EmbeddingProvider
from ingestion.embeddings.cohere_bedrock import CohereBedrockProvider
from ingestion.embeddings.fake import FakeEmbeddingProvider

SETTINGS = EmbeddingSettings()


@pytest.mark.parametrize(
    "provider",
    [
        FakeEmbeddingProvider(SETTINGS.dimension),
        CohereBedrockProvider(MagicMock(), SETTINGS),
    ],
    ids=["fake", "cohere_bedrock"],
)
class TestEmbeddingProviderConformance:
    def test_provider_satisfies_embedding_provider_protocol(self, provider):
        assert isinstance(provider, EmbeddingProvider)

    def test_provider_exposes_model_id_and_dimension(self, provider):
        assert isinstance(provider.model_id, str)
        assert isinstance(provider.dimension, int)
        assert provider.dimension > 0
