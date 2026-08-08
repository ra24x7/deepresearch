from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import Base, Chunk, Claim, Paper
from db.queries import arxiv_ids_in_corpus, chunks_by_paper, claims_by_paper, raw_text_by_paper


def _paper(arxiv_id: str, corpus: str) -> Paper:
    return Paper(
        arxiv_id=arxiv_id,
        title="A Paper",
        authors=["Jane Doe"],
        abstract="An abstract.",
        categories=["cs.IR"],
        published=date(2026, 1, 1),
        corpus=corpus,
        raw_text=f"full text of {arxiv_id}",
        sections=[],
        page_count=1,
    )


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add_all([_paper("2602.00002", "evalv1"), _paper("2602.00001", "evalv1"), _paper("2602.00003", "other")])
    session.add_all(
        [
            Chunk(chunk_id="c1", arxiv_id="2602.00001", section_title="Method", part_index=0, word_count=2, text="a b"),
            Chunk(chunk_id="c2", arxiv_id="2602.00001", section_title="Method", part_index=1, word_count=2, text="c d"),
            Chunk(chunk_id="c3", arxiv_id="2602.00002", section_title="Intro", part_index=0, word_count=2, text="e f"),
        ]
    )
    session.add_all(
        [
            Claim(claim_hash="h1", arxiv_id="2602.00001", claim_text="a claim", section_title="Method"),
            Claim(claim_hash="h2", arxiv_id="2602.00002", claim_text="another claim", section_title="Intro"),
        ]
    )
    session.commit()
    yield session
    session.close()
    engine.dispose()


class TestChunksByPaper:
    def test_groups_id_text_pairs_under_their_paper(self, session):
        assert chunks_by_paper(session) == {
            "2602.00001": [("c1", "a b"), ("c2", "c d")],
            "2602.00002": [("c3", "e f")],
        }

    def test_a_paper_without_chunks_reads_as_empty(self, session):
        assert chunks_by_paper(session)["2602.00003"] == []


class TestClaimsByPaper:
    def test_keys_claims_by_hash(self, session):
        assert claims_by_paper(session) == {
            "2602.00001": [("h1", "a claim")],
            "2602.00002": [("h2", "another claim")],
        }


class TestRawTextByPaper:
    def test_maps_every_paper_to_its_parsed_text(self, session):
        assert raw_text_by_paper(session)["2602.00001"] == "full text of 2602.00001"


class TestArxivIdsInCorpus:
    def test_returns_only_the_requested_corpus_sorted(self, session):
        assert arxiv_ids_in_corpus(session, "evalv1") == ["2602.00001", "2602.00002"]

    def test_an_unknown_corpus_is_empty(self, session):
        assert arxiv_ids_in_corpus(session, "nope") == []
