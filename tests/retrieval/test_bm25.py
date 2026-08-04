from unittest.mock import MagicMock

from retrieval.channels.bm25 import search_bm25
from search.indices import chunks_index_name


def _response(hits: list[dict]) -> dict:
    return {"hits": {"hits": hits}}


def _hit(**source) -> dict:
    base = {
        "chunk_id": "c1",
        "arxiv_id": "2501.00001",
        "section_title": "Method",
        "text": "attention is all you need",
        "page_start": 3,
        "page_end": 4,
    }
    return {"_score": 7.5, "_source": {**base, **source}}


class TestQueryBody:
    def test_targets_the_chunks_index_for_the_corpus(self):
        client = MagicMock()
        client.search.return_value = _response([])

        search_bm25(client, "arxiv2025", "sparse attention", size=5)

        assert client.search.call_args.kwargs["index"] == chunks_index_name("arxiv2025")

    def test_matches_the_query_against_the_text_field(self):
        client = MagicMock()
        client.search.return_value = _response([])

        search_bm25(client, "arxiv2025", "sparse attention", size=5)

        body = client.search.call_args.kwargs["body"]
        assert body["query"] == {"match": {"text": "sparse attention"}}

    def test_passes_size_through(self):
        client = MagicMock()
        client.search.return_value = _response([])

        search_bm25(client, "arxiv2025", "sparse attention", size=17)

        assert client.search.call_args.kwargs["body"]["size"] == 17


class TestHitMapping:
    def test_maps_source_fields_onto_retrieval_hit(self):
        client = MagicMock()
        client.search.return_value = _response([_hit()])

        hits = search_bm25(client, "arxiv2025", "attention", size=5)

        assert len(hits) == 1
        hit = hits[0]
        assert hit.doc_id == "c1"
        assert hit.arxiv_id == "2501.00001"
        assert hit.channel == "bm25"
        assert hit.score == 7.5
        assert hit.text == "attention is all you need"
        assert hit.section_title == "Method"
        assert hit.page_start == 3
        assert hit.page_end == 4

    def test_preserves_result_order(self):
        client = MagicMock()
        client.search.return_value = _response([_hit(chunk_id="c1"), _hit(chunk_id="c2")])

        hits = search_bm25(client, "arxiv2025", "attention", size=5)

        assert [hit.doc_id for hit in hits] == ["c1", "c2"]

    def test_empty_result_set_returns_empty_list(self):
        client = MagicMock()
        client.search.return_value = _response([])

        assert search_bm25(client, "arxiv2025", "attention", size=5) == []

    def test_missing_page_fields_become_none(self):
        client = MagicMock()
        source = {
            "chunk_id": "c9",
            "arxiv_id": "2501.00002",
            "text": "no pages recorded",
        }
        client.search.return_value = _response([{"_score": 1.25, "_source": source}])

        hits = search_bm25(client, "arxiv2025", "attention", size=5)

        assert hits[0].page_start is None
        assert hits[0].page_end is None
        assert hits[0].section_title == ""
