import math

from ingestion.embeddings.fake import FakeEmbeddingProvider


class TestFakeEmbeddingProvider:
    def test_model_id_is_fake(self):
        provider = FakeEmbeddingProvider(dimension=8)

        assert provider.model_id == "fake"

    def test_embed_query_returns_vector_of_configured_dimension(self):
        provider = FakeEmbeddingProvider(dimension=16)

        vector = provider.embed_query("hello")

        assert len(vector) == 16
        assert provider.dimension == 16

    def test_embed_query_is_unit_norm(self):
        provider = FakeEmbeddingProvider(dimension=32)

        vector = provider.embed_query("hello world")

        norm = math.sqrt(sum(v * v for v in vector))
        assert math.isclose(norm, 1.0, rel_tol=1e-9)

    def test_same_text_produces_same_vector(self):
        provider = FakeEmbeddingProvider(dimension=8)

        assert provider.embed_query("same text") == provider.embed_query("same text")

    def test_different_texts_produce_different_vectors(self):
        provider = FakeEmbeddingProvider(dimension=8)

        assert provider.embed_query("text a") != provider.embed_query("text b")

    def test_embed_passages_returns_one_vector_per_text_in_order(self):
        provider = FakeEmbeddingProvider(dimension=8)

        vectors = provider.embed_passages(["a", "b", "c"])

        assert len(vectors) == 3
        assert vectors[0] == provider.embed_query("a")
        assert vectors[2] == provider.embed_query("c")

    def test_embed_passages_empty_list_returns_empty_list(self):
        provider = FakeEmbeddingProvider(dimension=8)

        assert provider.embed_passages([]) == []
