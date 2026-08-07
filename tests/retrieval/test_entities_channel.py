import json
import math
from unittest.mock import MagicMock

from retrieval.channels.entities import search_entities
from search.indices import entities_index_name


def _entity_hit(
    entity_key: str,
    score: float,
    link_count: int,
    chunk_ids: list[str],
    surface_forms: list[str] | None = None,
    arxiv_ids: list[str] | None = None,
) -> dict:
    return {
        "_score": score,
        "_source": {
            "entity_key": entity_key,
            "entity_type": "model",
            "surface_forms": surface_forms if surface_forms is not None else [entity_key],
            "link_count": link_count,
            "linked_arxiv_ids": arxiv_ids if arxiv_ids is not None else [c.split("::")[0] for c in chunk_ids],
            "linked_chunk_ids": chunk_ids,
        },
    }


def _client(hits: list[dict]) -> MagicMock:
    client = MagicMock()
    client.search.return_value = {"hits": {"hits": hits}}
    return client


class TestDamping:
    def test_common_entity_scores_below_rare_entity_with_same_base_score(self):
        client = _client(
            [
                _entity_hit("transformer", score=10.0, link_count=100, chunk_ids=["2501.00001::intro::0"]),
                _entity_hit("mamba-2", score=10.0, link_count=1, chunk_ids=["2501.00002::intro::0"]),
            ]
        )

        hits = search_entities(client, "corpusA", "mamba-2", size=10)

        assert [hit.doc_id for hit in hits] == ["2501.00002::intro::0", "2501.00001::intro::0"]
        assert hits[0].score > hits[1].score

    def test_score_is_base_divided_by_log_damped_link_count(self):
        client = _client([_entity_hit("bert", score=8.0, link_count=7, chunk_ids=["2501.00001::intro::0"])])

        hits = search_entities(client, "corpusA", "bert", size=10)

        assert hits[0].score == 8.0 / (1 + math.log(8))

    def test_damping_zero_leaves_base_score_untouched(self):
        client = _client([_entity_hit("bert", score=8.0, link_count=7, chunk_ids=["2501.00001::intro::0"])])

        hits = search_entities(client, "corpusA", "bert", size=10, damping=0.0)

        assert hits[0].score == 8.0

    def test_damping_strength_scales_the_penalty(self):
        client = _client([_entity_hit("bert", score=8.0, link_count=7, chunk_ids=["2501.00001::intro::0"])])

        weak = search_entities(client, "corpusA", "bert", size=10, damping=0.5)
        strong = search_entities(client, "corpusA", "bert", size=10, damping=2.0)

        assert weak[0].score > strong[0].score


class TestHitExpansion:
    def test_emits_one_hit_per_linked_chunk_id(self):
        chunk_ids = ["2501.00001::intro::0", "2501.00001::methods::1", "2501.00002::intro::0"]
        client = _client([_entity_hit("bert", score=5.0, link_count=2, chunk_ids=chunk_ids)])

        hits = search_entities(client, "corpusA", "bert", size=10)

        assert [hit.doc_id for hit in hits] == chunk_ids

    def test_arxiv_id_is_parsed_from_the_chunk_id_prefix(self):
        client = _client(
            [
                _entity_hit(
                    "bert",
                    score=5.0,
                    link_count=2,
                    chunk_ids=["2501.00001::intro::0", "2501.00002::methods::1"],
                    arxiv_ids=["2501.00001", "2501.00002"],
                )
            ]
        )

        hits = search_entities(client, "corpusA", "bert", size=10)

        assert [hit.arxiv_id for hit in hits] == ["2501.00001", "2501.00002"]

    def test_falls_back_to_the_sole_linked_arxiv_id_when_chunk_id_has_no_prefix(self):
        client = _client(
            [_entity_hit("bert", score=5.0, link_count=1, chunk_ids=["legacy-chunk-7"], arxiv_ids=["2501.00009"])]
        )

        hits = search_entities(client, "corpusA", "bert", size=10)

        assert hits[0].arxiv_id == "2501.00009"

    def test_arxiv_id_is_empty_when_neither_chunk_id_nor_links_resolve_it(self):
        client = _client([_entity_hit("bert", score=5.0, link_count=2, chunk_ids=["legacy-chunk-7"], arxiv_ids=[])])

        hits = search_entities(client, "corpusA", "bert", size=10)

        assert hits[0].arxiv_id == ""

    def test_text_is_the_entity_surface_form_and_channel_is_entities(self):
        client = _client(
            [
                _entity_hit(
                    "bert",
                    score=5.0,
                    link_count=1,
                    chunk_ids=["2501.00001::intro::0"],
                    surface_forms=["BERT", "Bert"],
                )
            ]
        )

        hits = search_entities(client, "corpusA", "BERT", size=10)

        assert hits[0].text == "BERT"
        assert hits[0].channel == "entities"

    def test_entity_without_linked_chunks_produces_no_hits(self):
        client = _client([_entity_hit("bert", score=5.0, link_count=0, chunk_ids=[])])

        assert search_entities(client, "corpusA", "bert", size=10) == []


class TestSizeAndOrdering:
    def test_results_are_capped_at_size(self):
        chunk_ids = [f"2501.00001::intro::{i}" for i in range(9)]
        client = _client([_entity_hit("bert", score=5.0, link_count=9, chunk_ids=chunk_ids)])

        hits = search_entities(client, "corpusA", "bert", size=4)

        assert len(hits) == 4

    def test_results_are_sorted_by_damped_score_descending(self):
        client = _client(
            [
                _entity_hit("transformer", score=20.0, link_count=5000, chunk_ids=["2501.00001::intro::0"]),
                _entity_hit("mamba-2", score=4.0, link_count=1, chunk_ids=["2501.00002::intro::0"]),
                _entity_hit("s4", score=9.0, link_count=3, chunk_ids=["2501.00003::intro::0"]),
            ]
        )

        hits = search_entities(client, "corpusA", "mamba-2", size=10)

        assert [hit.score for hit in hits] == sorted((hit.score for hit in hits), reverse=True)
        assert hits[0].doc_id == "2501.00003::intro::0"

    def test_returns_empty_list_when_nothing_matches(self):
        assert search_entities(_client([]), "corpusA", "nothing here", size=10) == []


class TestQuery:
    def test_searches_the_corpus_entities_index(self):
        client = _client([])

        search_entities(client, "corpusA", "BERT", size=10)

        assert client.search.call_args.kwargs["index"] == entities_index_name("corpusA")

    def test_query_body_carries_the_normalized_query_text(self):
        client = _client([])

        search_entities(client, "corpusA", "  Mamba–2  ", size=10)

        body = json.dumps(client.search.call_args.kwargs["body"])
        assert "mamba-2" in body

    def test_does_not_mutate_the_opensearch_response(self):
        response_hits = [_entity_hit("bert", score=5.0, link_count=1, chunk_ids=["2501.00001::intro::0"])]
        snapshot = json.dumps(response_hits)

        search_entities(_client(response_hits), "corpusA", "bert", size=10)

        assert json.dumps(response_hits) == snapshot


class TestMentionExtraction:
    def _terms_sent(self, client) -> set[str]:
        body = client.search.call_args[1]["body"]
        return set(body["query"]["bool"]["should"][0]["terms"]["entity_key"])

    def test_an_entity_inside_a_natural_language_question_is_probed(self):
        # the whole query is never an entity key, so matching the query string
        # itself found nothing for any real question.
        client = _client([_entity_hit("a-rag", 1.0, 1, ["2602.03442::intro::0"])])

        search_entities(client, "evalv1", "What three retrieval tools does the A-RAG framework provide?", 10)

        assert "a-rag" in self._terms_sent(client)

    def test_multi_word_entities_are_probed_as_phrases(self):
        client = _client([])

        search_entities(client, "evalv1", "how does retrieval-augmented generation handle long context?", 10)

        terms = self._terms_sent(client)
        assert "retrieval-augmented generation" in terms
        assert "long context" in terms

    def test_trailing_punctuation_is_stripped_from_candidates(self):
        client = _client([])

        search_entities(client, "evalv1", "what is BM25?", 10)

        assert "bm25" in self._terms_sent(client)

    def test_metric_names_with_symbols_survive(self):
        client = _client([])

        search_entities(client, "evalv1", "what NDCG@10 does it report?", 10)

        assert "ndcg@10" in self._terms_sent(client)

    def test_candidate_count_is_bounded_for_a_long_query(self):
        client = _client([])
        long_query = " ".join(f"word{i}" for i in range(80))

        search_entities(client, "evalv1", long_query, 10)

        assert len(self._terms_sent(client)) <= 400


class TestDocumentFrequencyFilter:
    def test_entities_above_the_frequency_ceiling_are_excluded_in_the_query(self):
        # damping scales the score, but RRF fuses by RANK — a damped generic
        # entity still lands at rank 0 of its channel and contributes fully.
        # Non-discriminative entities have to be kept out, not merely scored down.
        client = _client([])

        search_entities(client, "evalv1", "what accuracy does it report?", 10, max_link_count=20)

        body = client.search.call_args[1]["body"]
        assert body["query"]["bool"]["filter"] == [{"range": {"link_count": {"lte": 20}}}]

    def test_no_filter_is_applied_when_the_ceiling_is_unset(self):
        client = _client([])

        search_entities(client, "evalv1", "what accuracy does it report?", 10)

        assert "filter" not in client.search.call_args[1]["body"]["query"]["bool"]
