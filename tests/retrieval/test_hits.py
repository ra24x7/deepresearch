from retrieval.channels.hits import chunk_hit, claim_hit


def _raw(**source) -> dict:
    return {"_score": 4.5, "_source": source}


class TestChunkHit:
    def test_maps_the_chunk_document_onto_the_requested_channel(self):
        hit = chunk_hit(
            _raw(
                chunk_id="c1",
                arxiv_id="2602.00001",
                text="attention is all you need",
                section_title="Method",
                page_start=3,
                page_end=4,
            ),
            "dense_chunks",
        )

        assert (hit.doc_id, hit.arxiv_id, hit.channel, hit.score) == ("c1", "2602.00001", "dense_chunks", 4.5)
        assert (hit.section_title, hit.page_start, hit.page_end) == ("Method", 3, 4)

    def test_absent_optional_fields_do_not_raise(self):
        hit = chunk_hit(_raw(chunk_id="c1", arxiv_id="2602.00001", text="body"), "bm25")

        assert hit.section_title == ""
        assert hit.page_start is None
        assert hit.page_end is None

    def test_a_null_section_title_reads_as_empty(self):
        hit = chunk_hit(_raw(chunk_id="c1", arxiv_id="2602.00001", text="body", section_title=None), "bm25")

        assert hit.section_title == ""


class TestClaimHit:
    def test_keys_on_claim_hash_and_carries_the_claim_text(self):
        hit = claim_hit(_raw(claim_hash="h1", arxiv_id="2602.00001", claim_text="a claim", section_title="Intro"))

        assert (hit.doc_id, hit.channel, hit.text) == ("h1", "dense_claims", "a claim")

    def test_a_claim_has_no_page_range(self):
        hit = claim_hit(_raw(claim_hash="h1", arxiv_id="2602.00001", claim_text="a claim"))

        assert hit.page_start is None
        assert hit.page_end is None
