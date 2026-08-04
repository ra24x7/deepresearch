from unittest.mock import MagicMock

from ingestion.embeddings.fake import FakeEmbeddingProvider
from retrieval.channels.dense import search_dense_chunks, search_dense_claims
from search.indices import chunks_index_name, claims_index_name

DIMENSION = 1024


def _response(sources: list[dict], scores: list[float] | None = None) -> dict:
    scores = scores or [1.0] * len(sources)
    return {"hits": {"hits": [{"_score": score, "_source": source} for source, score in zip(sources, scores)]}}


def _chunk_source(chunk_id: str = "2501.00001:3") -> dict:
    return {
        "chunk_id": chunk_id,
        "arxiv_id": "2501.00001",
        "section_title": "Method",
        "text": "the chunk body",
        "page_start": 4,
        "page_end": 5,
    }


def _claim_source(claim_hash: str = "abc123") -> dict:
    return {
        "claim_hash": claim_hash,
        "arxiv_id": "2501.00002",
        "section_title": "Results",
        "claim_text": "the claim body",
    }


class TestQueryEmbedding:
    def test_embeds_query_exactly_once_for_chunks(self):
        client = MagicMock()
        client.search.return_value = _response([])
        provider = MagicMock(wraps=FakeEmbeddingProvider(DIMENSION))

        search_dense_chunks(client, "corpusA", provider, "what is the loss?", size=5)

        provider.embed_query.assert_called_once_with("what is the loss?")

    def test_embeds_query_exactly_once_for_claims(self):
        client = MagicMock()
        client.search.return_value = _response([])
        provider = MagicMock(wraps=FakeEmbeddingProvider(DIMENSION))

        search_dense_claims(client, "corpusA", provider, "what is the loss?", size=5)

        provider.embed_query.assert_called_once_with("what is the loss?")


class TestKnnBody:
    def test_chunks_body_carries_query_vector_and_k(self):
        client = MagicMock()
        client.search.return_value = _response([])
        provider = FakeEmbeddingProvider(DIMENSION)
        expected_vector = provider.embed_query("query text")

        search_dense_chunks(client, "corpusA", provider, "query text", size=7)

        kwargs = client.search.call_args.kwargs
        assert kwargs["index"] == chunks_index_name("corpusA")
        knn = kwargs["body"]["query"]["knn"]["embedding"]
        assert knn["vector"] == expected_vector
        assert knn["k"] == 7
        assert kwargs["body"]["size"] == 7

    def test_claims_body_carries_query_vector_and_k(self):
        client = MagicMock()
        client.search.return_value = _response([])
        provider = FakeEmbeddingProvider(DIMENSION)
        expected_vector = provider.embed_query("query text")

        search_dense_claims(client, "corpusA", provider, "query text", size=3)

        kwargs = client.search.call_args.kwargs
        assert kwargs["index"] == claims_index_name("corpusA")
        knn = kwargs["body"]["query"]["knn"]["embedding"]
        assert knn["vector"] == expected_vector
        assert knn["k"] == 3


class TestChunkMapping:
    def test_maps_source_to_dense_chunks_hit(self):
        client = MagicMock()
        client.search.return_value = _response([_chunk_source()], [0.82])

        hits = search_dense_chunks(client, "corpusA", FakeEmbeddingProvider(DIMENSION), "q", size=5)

        assert len(hits) == 1
        hit = hits[0]
        assert hit.channel == "dense_chunks"
        assert hit.doc_id == "2501.00001:3"
        assert hit.arxiv_id == "2501.00001"
        assert hit.text == "the chunk body"
        assert hit.section_title == "Method"
        assert hit.score == 0.82
        assert (hit.page_start, hit.page_end) == (4, 5)

    def test_defaults_missing_optional_fields(self):
        client = MagicMock()
        source = {"chunk_id": "c1", "arxiv_id": "2501.00001", "text": "body"}
        client.search.return_value = _response([source])

        hit = search_dense_chunks(client, "corpusA", FakeEmbeddingProvider(DIMENSION), "q", size=5)[0]

        assert hit.section_title == ""
        assert hit.page_start is None
        assert hit.page_end is None

    def test_preserves_result_order(self):
        client = MagicMock()
        client.search.return_value = _response([_chunk_source("c1"), _chunk_source("c2")], [0.9, 0.4])

        hits = search_dense_chunks(client, "corpusA", FakeEmbeddingProvider(DIMENSION), "q", size=5)

        assert [hit.doc_id for hit in hits] == ["c1", "c2"]


class TestClaimMapping:
    def test_maps_source_to_dense_claims_hit(self):
        client = MagicMock()
        client.search.return_value = _response([_claim_source()], [0.55])

        hits = search_dense_claims(client, "corpusA", FakeEmbeddingProvider(DIMENSION), "q", size=5)

        assert len(hits) == 1
        hit = hits[0]
        assert hit.channel == "dense_claims"
        assert hit.doc_id == "abc123"
        assert hit.arxiv_id == "2501.00002"
        assert hit.text == "the claim body"
        assert hit.section_title == "Results"
        assert hit.score == 0.55

    def test_leaves_claim_pages_unset(self):
        client = MagicMock()
        client.search.return_value = _response([_claim_source()])

        hit = search_dense_claims(client, "corpusA", FakeEmbeddingProvider(DIMENSION), "q", size=5)[0]

        assert hit.page_start is None
        assert hit.page_end is None


class TestEmptyResults:
    def test_chunks_returns_empty_list(self):
        client = MagicMock()
        client.search.return_value = _response([])

        assert search_dense_chunks(client, "corpusA", FakeEmbeddingProvider(DIMENSION), "q", size=5) == []

    def test_claims_returns_empty_list(self):
        client = MagicMock()
        client.search.return_value = {}

        assert search_dense_claims(client, "corpusA", FakeEmbeddingProvider(DIMENSION), "q", size=5) == []
