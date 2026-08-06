import pytest

from evals.retrieval_eval import (
    ChannelScore,
    dcg,
    ndcg_at_k,
    recall_at_k,
    relevant_chunk_ids,
    score_question,
)
from retrieval.schemas import FusedHit, RetrievalHit


def _chunks(*pairs: tuple[str, str]) -> list[tuple[str, str]]:
    return list(pairs)


class TestRelevantChunkIds:
    def test_every_chunk_containing_the_quote_is_relevant(self):
        # our own 100-word overlap puts some quotes in two chunks; pinning one
        # id would score a correct retrieval as a miss.
        chunks = _chunks(
            ("c1", "irrelevant text"),
            ("c2", "prefix ... the model achieves near-perfect accuracy ... suffix"),
            ("c3", "the model achieves near-perfect accuracy on both subtasks"),
        )

        ids = relevant_chunk_ids("the model achieves near-perfect accuracy", chunks)

        assert ids == {"c2", "c3"}

    def test_typography_differences_still_match(self):
        chunks = _chunks(("c1", "we use trans-\nformers for eﬃcient search"))

        ids = relevant_chunk_ids("we use transformers for efficient search", chunks)

        assert ids == {"c1"}

    def test_no_match_returns_empty(self):
        assert relevant_chunk_ids("absent phrase", _chunks(("c1", "other text"))) == set()


class TestMetrics:
    def test_recall_counts_any_relevant_id_in_the_top_k(self):
        ranked = ["a", "b", "c", "d"]

        assert recall_at_k(ranked, {"c"}, k=3) == 1.0
        assert recall_at_k(ranked, {"d"}, k=3) == 0.0

    def test_recall_is_fractional_when_several_ids_are_relevant(self):
        assert recall_at_k(["a", "b"], {"a", "z"}, k=2) == pytest.approx(0.5)

    def test_recall_of_an_empty_ranking_is_zero(self):
        assert recall_at_k([], {"a"}, k=10) == 0.0

    def test_no_relevant_ids_yields_none_so_it_can_be_excluded(self):
        assert recall_at_k(["a"], set(), k=10) is None

    def test_dcg_rewards_earlier_positions(self):
        assert dcg(["a", "x"], {"a"}) > dcg(["x", "a"], {"a"})

    def test_ndcg_is_one_when_all_relevant_docs_lead(self):
        assert ndcg_at_k(["a", "b", "x"], {"a", "b"}, k=3) == pytest.approx(1.0)

    def test_ndcg_is_zero_when_nothing_relevant_is_retrieved(self):
        assert ndcg_at_k(["x", "y"], {"a"}, k=2) == 0.0


class TestScoreQuestion:
    def test_scores_each_channel_and_the_fused_ranking(self):
        by_channel = {
            "bm25": [RetrievalHit(doc_id="miss", arxiv_id="p", channel="bm25", score=1.0, text="t")],
            "dense_chunks": [RetrievalHit(doc_id="gold", arxiv_id="p", channel="dense_chunks", score=1.0, text="t")],
        }
        fused = [FusedHit(doc_id="gold", arxiv_id="p", score=1.0, text="t", channels=("dense_chunks",))]

        result = score_question(by_channel, fused, relevant={"gold"}, k=10)

        assert result.per_channel["dense_chunks"].recall == 1.0
        assert result.per_channel["bm25"].recall == 0.0
        assert result.fused.recall == 1.0

    def test_reports_whether_the_answer_was_reachable_at_all(self):
        # a chunk missed by every channel can never be recovered by reranking
        by_channel = {"bm25": [RetrievalHit(doc_id="x", arxiv_id="p", channel="bm25", score=1.0, text="t")]}

        result = score_question(by_channel, [], relevant={"gold"}, k=10)

        assert result.reachable is False

    def test_channel_score_is_none_when_the_question_has_no_relevant_chunk(self):
        result = score_question({}, [], relevant=set(), k=10)

        assert result.fused is None or result.fused.recall is None


class TestChannelScore:
    def test_carries_recall_and_ndcg(self):
        score = ChannelScore(recall=0.5, ndcg=0.25, retrieved=4)

        assert (score.recall, score.ndcg, score.retrieved) == (0.5, 0.25, 4)
