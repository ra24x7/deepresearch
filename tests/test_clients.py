import pytest

from clients import embedding_provider, opensearch_client
from config import EmbeddingSettings, OpenSearchSettings
from ingestion.embeddings.exceptions import UnknownEmbeddingProviderError


def _host(client) -> tuple[str, int]:
    connection = client.transport.hosts[0]
    return connection["host"], connection["port"]


class TestOpenSearchClient:
    def test_reads_host_and_port_from_settings(self):
        client = opensearch_client(OpenSearchSettings(host="opensearch:9201"))

        assert _host(client) == ("opensearch", 9201)

    @pytest.mark.parametrize("scheme", ["http://", "https://"])
    def test_a_scheme_in_the_configured_host_is_stripped(self, scheme):
        client = opensearch_client(OpenSearchSettings(host=f"{scheme}opensearch:9201"))

        assert _host(client) == ("opensearch", 9201)

    def test_a_host_without_a_port_falls_back_to_the_default(self):
        client = opensearch_client(OpenSearchSettings(host="opensearch"))

        assert _host(client) == ("opensearch", 9200)


class TestEmbeddingProvider:
    def test_the_fake_provider_needs_no_bedrock_client(self):
        # a dry run must reach the whole path without credentials
        provider = embedding_provider(EmbeddingSettings(provider="fake", dimension=8))

        assert provider.model_id == "fake"
        assert len(provider.embed_query("a query")) == 8

    def test_a_hosted_provider_is_given_the_injected_client(self, mocker):
        build_client = mocker.patch("clients.bedrock_runtime_client")
        sentinel = object()

        provider = embedding_provider(EmbeddingSettings(provider="cohere_bedrock"), bedrock_client=sentinel)

        assert provider._client is sentinel
        build_client.assert_not_called()

    def test_a_hosted_provider_without_a_client_builds_one(self, mocker):
        build_client = mocker.patch("clients.bedrock_runtime_client")

        embedding_provider(EmbeddingSettings(provider="cohere_bedrock"))

        build_client.assert_called_once()

    def test_an_unknown_provider_is_rejected(self):
        with pytest.raises(UnknownEmbeddingProviderError):
            embedding_provider(EmbeddingSettings(provider="nope"))
