import pytest

from evals.retrieval_eval import (
    ChannelScore,
    dcg,
    ndcg_at_k,
    recall_at_k,
    relevant_chunk_ids,
    relevant_chunks_for_entry,
    relevant_claim_hashes,
    relevant_claims_for_entry,
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


class TestRelevantClaims:
    def test_a_claim_stating_the_answer_is_relevant(self):
        claims = [
            ("h1", "The graph contains 96,517 nodes and 84,222 edges across 14 types."),
            ("h2", "The system uses a LangGraph state machine for orchestration."),
        ]

        ids = relevant_claim_hashes(
            quote="The graph contains 96,517 nodes and 84,222 edges across 14 types",
            answer="96,517 nodes and 84,222 edges",
            claims=claims,
        )

        assert ids == {"h1"}

    def test_a_paraphrased_claim_still_counts(self):
        claims = [("h1", "Its knowledge graph holds 96,517 nodes and 84,222 edges.")]

        ids = relevant_claim_hashes(
            quote="The graph contains 96,517 nodes and 84,222 edges across 14 types",
            answer="96,517 nodes and 84,222 edges",
            claims=claims,
        )

        assert ids == {"h1"}

    def test_a_topically_similar_claim_without_the_fact_is_not_relevant(self):
        # the channel earns its place by carrying answers, not by being on-topic
        claims = [("h1", "The knowledge graph supports entity lookups and path traversals.")]

        ids = relevant_claim_hashes(
            quote="The graph contains 96,517 nodes and 84,222 edges across 14 types",
            answer="96,517 nodes and 84,222 edges",
            claims=claims,
        )

        assert ids == set()

    def test_no_claims_yields_an_empty_set(self):
        assert relevant_claim_hashes(quote="q", answer="a", claims=[]) == set()


ENTRY = {
    "id": "g001",
    "question": "how many nodes does the graph contain?",
    "reference_answer": "96,517 nodes",
    "evidence": [
        {"arxiv_id": "p1", "quote": "the graph contains 96,517 nodes"},
        {"arxiv_id": "p2", "quote": "the second paper reports the same count"},
        {"arxiv_id": "p3", "formula": "n = 96517"},
    ],
}


class TestRelevanceForAnEntry:

    def test_unions_the_chunks_of_every_quoted_evidence_item(self):
        chunks = {
            "p1": [("c1", "prefix the graph contains 96,517 nodes suffix")],
            "p2": [("c2", "the second paper reports the same count")],
            "p3": [("c3", "n = 96517")],
        }

        assert relevant_chunks_for_entry(ENTRY, chunks) == {"c1", "c2"}

    def test_evidence_without_a_quote_contributes_nothing(self):
        # a formula is a linearized transcription: there is no verbatim span
        assert relevant_chunks_for_entry(ENTRY, {"p3": [("c3", "n = 96517")]}) == set()

    def test_a_paper_with_no_chunks_loaded_is_skipped(self):
        assert relevant_chunks_for_entry(ENTRY, {}) == set()

    def test_claims_are_matched_against_quote_and_reference_answer(self):
        claims = {"p1": [("h1", "The graph contains 96,517 nodes."), ("h2", "The system uses LangGraph.")]}

        assert relevant_claims_for_entry(ENTRY, claims) == {"h1"}

    def test_an_entry_without_evidence_has_no_relevant_documents(self):
        assert relevant_chunks_for_entry({"id": "g002"}, {}) == set()
        assert relevant_claims_for_entry({"id": "g002"}, {}) == set()
