from unittest.mock import MagicMock

import pytest

from config import RetrievalSettings
from ingestion.embeddings.fake import FakeEmbeddingProvider
from retrieval.rerank.identity import IdentityReranker
from retrieval.schemas import RetrievalHit
from retrieval.search import search

PROVIDER = FakeEmbeddingProvider(1024)
SETTINGS = RetrievalSettings(top_k=3, over_fetch_multiplier=4, min_candidates=12)


def _hit(doc_id: str, channel: str, score: float) -> RetrievalHit:
    return RetrievalHit(
        doc_id=doc_id, arxiv_id="2602.03442", channel=channel, score=score, text=f"text of {doc_id}"
    )


@pytest.fixture
def channels(mocker):
    """Stub every channel so no OpenSearch call is made."""
    return {
        "bm25": mocker.patch("retrieval.search.search_bm25", return_value=[]),
        "dense_chunks": mocker.patch("retrieval.search.search_dense_chunks", return_value=[]),
        "dense_claims": mocker.patch("retrieval.search.search_dense_claims", return_value=[]),
        "entities": mocker.patch("retrieval.search.search_entities", return_value=[]),
    }


class TestRouting:
    def test_out_of_domain_queries_never_reach_a_channel(self, channels):
        result = search("what is the weather today?", "evalv1", MagicMock(), PROVIDER, IdentityReranker(), SETTINGS)

        assert result.route == "out_of_domain"
        assert result.hits == ()
        for stub in channels.values():
            stub.assert_not_called()

    def test_a_semantic_query_fans_out_to_every_channel(self, channels):
        search("how do agents choose retrieval tools?", "evalv1", MagicMock(), PROVIDER, IdentityReranker(), SETTINGS)

        for name, stub in channels.items():
            assert stub.called, f"{name} was not queried"

    def test_the_route_is_reported_on_the_result(self, channels):
        result = search("how does the method work?", "evalv1", MagicMock(), PROVIDER, IdentityReranker(), SETTINGS)

        assert result.route == "semantic"


class TestOverFetch:
    def test_channels_are_asked_for_more_candidates_than_top_k(self, channels):
        search("how does the method work?", "evalv1", MagicMock(), PROVIDER, IdentityReranker(), SETTINGS)

        # max(4 * 3, 12) = 12, never merely top_k: the reranker can only reorder
        # what stage one retrieved.
        for name, stub in channels.items():
            assert 12 in stub.call_args[0], f"{name} was not asked for 12 candidates"


class TestResults:
    def test_hits_are_capped_at_top_k(self, channels, mocker):
        many = [_hit(f"c{i}", "dense_chunks", 1.0 - i / 100) for i in range(10)]
        channels["dense_chunks"].return_value = many

        result = search("how does it work?", "evalv1", MagicMock(), PROVIDER, IdentityReranker(), SETTINGS)

        assert len(result.hits) == 3

    def test_channel_counts_record_what_each_channel_contributed(self, channels):
        channels["bm25"].return_value = [_hit("a", "bm25", 5.0), _hit("b", "bm25", 4.0)]
        channels["dense_chunks"].return_value = [_hit("a", "dense_chunks", 0.9)]

        result = search("how does it work?", "evalv1", MagicMock(), PROVIDER, IdentityReranker(), SETTINGS)

        assert result.channel_counts["bm25"] == 2
        assert result.channel_counts["dense_chunks"] == 1
        assert result.channel_counts["entities"] == 0

    def test_the_semantic_gate_still_applies_end_to_end(self, channels):
        # a lexical-only doc must not survive the pipeline
        channels["bm25"].return_value = [_hit("lexical-only", "bm25", 99.0)]
        channels["dense_chunks"].return_value = [_hit("semantic", "dense_chunks", 0.5)]

        result = search("how does it work?", "evalv1", MagicMock(), PROVIDER, IdentityReranker(), SETTINGS)

        assert [h.doc_id for h in result.hits] == ["semantic"]

    def test_the_reranker_decides_the_final_order(self, channels):
        channels["dense_chunks"].return_value = [_hit("a", "dense_chunks", 0.9), _hit("b", "dense_chunks", 0.1)]
        reranker = MagicMock()
        reranker.model_id = "mock-reranker"
        reranker.rerank.side_effect = lambda q, hits, top_n: list(reversed(hits))[:top_n]

        result = search("how does it work?", "evalv1", MagicMock(), PROVIDER, reranker, SETTINGS)

        assert [h.doc_id for h in result.hits] == ["b", "a"]
        assert result.reranker_model == reranker.model_id

    def test_reranker_is_skipped_when_nothing_survives_fusion(self, channels):
        reranker = MagicMock()
        reranker.model_id = "mock-reranker"

        result = search("how does it work?", "evalv1", MagicMock(), PROVIDER, reranker, SETTINGS)

        assert result.hits == ()
        reranker.rerank.assert_not_called()


class TestChannelWeights:
    def test_configured_weights_reach_fusion(self, channels, mocker):
        spy = mocker.patch("retrieval.search.fuse", return_value=[])
        settings = RetrievalSettings(top_k=3, entity_weight=0.1)

        search("how does it work?", "evalv1", MagicMock(), PROVIDER, IdentityReranker(), settings)

        assert spy.call_args.kwargs["weights"]["entities"] == 0.1

    def test_entity_channel_is_a_tiebreaker_not_a_vote_by_default(self):
        # measured: at weight 1.0 fused recall@10 falls 0.966 -> 0.902
        assert RetrievalSettings().entity_weight < 0.25
