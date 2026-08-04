from retrieval.fusion import fuse
from retrieval.schemas import RetrievalHit


def _hit(doc_id: str, channel: str, text: str = "text", score: float = 1.0) -> RetrievalHit:
    return RetrievalHit(
        doc_id=doc_id,
        arxiv_id=doc_id.split("::")[0],
        channel=channel,
        score=score,
        text=text,
        section_title="Method",
        page_start=3,
        page_end=4,
    )


def test_returns_empty_list_for_empty_input():
    assert fuse({}) == []
    assert fuse({"bm25": [], "dense_chunks": []}) == []


def test_doc_found_by_two_channels_outranks_single_channel_doc_at_same_rank():
    fused = fuse(
        {
            "bm25": [_hit("2501.00001::0", "bm25")],
            "dense_chunks": [_hit("2501.00001::0", "dense_chunks"), _hit("2501.00002::0", "dense_chunks")],
        }
    )

    assert [hit.doc_id for hit in fused] == ["2501.00001::0", "2501.00002::0"]
    assert fused[0].score > fused[1].score


def test_weights_change_the_ordering():
    hits_by_channel = {
        "dense_chunks": [_hit("2501.00002::0", "dense_chunks"), _hit("2501.00001::0", "dense_chunks")],
        "bm25": [_hit("2501.00001::0", "bm25")],
    }

    assert [hit.doc_id for hit in fuse(hits_by_channel)] == ["2501.00001::0", "2501.00002::0"]

    downweighted = fuse(hits_by_channel, weights={"bm25": 0.01})
    assert [hit.doc_id for hit in downweighted] == ["2501.00002::0", "2501.00001::0"]


def test_gate_drops_lexical_only_doc_but_keeps_doc_backed_by_a_semantic_channel():
    fused = fuse(
        {
            "bm25": [_hit("2501.00009::0", "bm25", score=99.0), _hit("2501.00001::0", "bm25")],
            "dense_chunks": [_hit("2501.00001::0", "dense_chunks")],
        }
    )

    assert [hit.doc_id for hit in fused] == ["2501.00001::0"]


def test_gate_drops_everything_when_no_gate_channel_is_present():
    assert fuse({"bm25": [_hit("2501.00009::0", "bm25")], "entities": [_hit("2501.00009::0", "entities")]}) == []


def test_empty_gate_channels_disables_the_gate():
    fused = fuse(
        {
            "bm25": [_hit("2501.00009::0", "bm25")],
            "dense_chunks": [_hit("2501.00001::0", "dense_chunks")],
        },
        gate_channels=(),
    )

    assert sorted(hit.doc_id for hit in fused) == ["2501.00001::0", "2501.00009::0"]


def test_channels_tuple_records_every_channel_that_found_the_doc_in_input_order():
    fused = fuse(
        {
            "bm25": [_hit("2501.00001::0", "bm25")],
            "dense_chunks": [_hit("2501.00001::0", "dense_chunks")],
            "dense_claims": [_hit("2501.00001::0", "dense_claims")],
        }
    )

    assert fused[0].channels == ("bm25", "dense_chunks", "dense_claims")


def test_fields_are_taken_from_the_gate_channel_hit_when_available():
    fused = fuse(
        {
            "bm25": [_hit("2501.00001::0", "bm25", text="lexical text")],
            "dense_chunks": [_hit("2501.00001::0", "dense_chunks", text="semantic text")],
        }
    )

    assert fused[0].text == "semantic text"


def test_fields_fall_back_to_the_first_hit_seen_when_the_gate_is_disabled():
    fused = fuse(
        {
            "bm25": [_hit("2501.00009::0", "bm25", text="lexical text")],
            "entities": [_hit("2501.00009::0", "entities", text="entity text")],
        },
        gate_channels=(),
    )

    assert fused[0].text == "lexical text"


def test_top_k_truncates_to_the_highest_scoring_hits():
    fused = fuse(
        {
            "dense_chunks": [
                _hit("2501.00001::0", "dense_chunks"),
                _hit("2501.00002::0", "dense_chunks"),
                _hit("2501.00003::0", "dense_chunks"),
            ]
        },
        top_k=2,
    )

    assert [hit.doc_id for hit in fused] == ["2501.00001::0", "2501.00002::0"]


def test_rrf_contribution_uses_one_based_rank_offset_by_k():
    fused = fuse({"dense_chunks": [_hit("2501.00001::0", "dense_chunks"), _hit("2501.00002::0", "dense_chunks")]}, k=60)

    assert fused[0].score == 1.0 / 61
    assert fused[1].score == 1.0 / 62
