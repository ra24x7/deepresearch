from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import Base, Claim, Paper
from tools.metadata import category_counts, count_papers, get_claims, papers_by_year


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add_all(
        [
            _paper("2601.00001", ["cs.AI", "cs.CL"], date(2026, 2, 3), "evalv1"),
            _paper("2601.00002", ["cs.AI", "cs.IR"], date(2026, 5, 1), "evalv1"),
            _paper("2512.00003", ["cs.CL"], date(2025, 12, 9), "evalv1"),
            _paper("2607.00004", ["cs.AI"], date(2026, 7, 29), "sandbox"),
        ]
    )
    session.add_all(
        [
            Claim(claim_hash="h1", arxiv_id="2601.00001", claim_text="first claim", section_title="Method"),
            Claim(claim_hash="h2", arxiv_id="2601.00001", claim_text="second claim", section_title="Results"),
            Claim(claim_hash="h3", arxiv_id="2601.00002", claim_text="other paper", section_title="Method"),
        ]
    )
    session.commit()
    yield session
    session.close()
    engine.dispose()


def _paper(arxiv_id: str, categories: list[str], published: date, corpus: str) -> Paper:
    return Paper(
        arxiv_id=arxiv_id, title=f"title {arxiv_id}", authors=["A. Author"], abstract="abstract",
        categories=categories, published=published, corpus=corpus, raw_text="text",
        sections=[], page_count=10,
    )


class TestCountPapers:
    def test_counts_only_the_named_corpus(self, session):
        # the sandbox paper is deliberately outside evalv1 and must not be counted
        assert count_papers(session, "evalv1") == 3

    def test_counts_a_single_publication_year(self, session):
        assert count_papers(session, "evalv1", published_year=2026) == 2

    def test_a_year_with_no_papers_counts_zero(self, session):
        assert count_papers(session, "evalv1", published_year=2024) == 0

    def test_an_unknown_corpus_counts_zero(self, session):
        assert count_papers(session, "no-such-corpus") == 0


class TestPapersByYear:
    def test_years_are_returned_with_their_counts_oldest_first(self, session):
        assert papers_by_year(session, "evalv1") == [(2025, 1), (2026, 2)]


class TestCategoryCounts:
    def test_categories_are_counted_across_papers_most_frequent_first(self, session):
        # g038: "which arXiv category appears most often, and in how many papers"
        assert category_counts(session, "evalv1") == [("cs.AI", 2), ("cs.CL", 2), ("cs.IR", 1)]

    def test_a_paper_outside_the_corpus_contributes_nothing(self, session):
        counts = dict(category_counts(session, "evalv1"))

        assert counts["cs.AI"] == 2

    def test_ties_are_broken_by_category_name_so_the_answer_is_stable(self, session):
        names = [name for name, _ in category_counts(session, "evalv1")]

        assert names[:2] == ["cs.AI", "cs.CL"]


class TestGetClaims:
    def test_returns_every_claim_for_one_paper(self, session):
        claims = get_claims(session, "2601.00001")

        assert [c["claim_text"] for c in claims] == ["first claim", "second claim"]

    def test_each_claim_carries_its_section(self, session):
        assert get_claims(session, "2601.00001")[0]["section_title"] == "Method"

    def test_a_paper_with_no_claims_returns_an_empty_list(self, session):
        assert get_claims(session, "2512.00003") == []
