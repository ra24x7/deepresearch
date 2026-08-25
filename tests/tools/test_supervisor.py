from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import Base, Paper
from retrieval.schemas import FusedHit
from tools.exceptions import ConfirmationRequired
from tools.supervisor import dispatch, ingest_by_id, search_papers, sql_metadata


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add_all(
        [
            _paper("2601.00001", ["cs.AI", "cs.CL"], date(2026, 2, 3)),
            _paper("2601.00002", ["cs.AI", "cs.IR"], date(2026, 5, 1)),
            _paper("2512.00003", ["cs.CL"], date(2025, 12, 9)),
        ]
    )
    session.commit()
    yield session
    session.close()
    engine.dispose()


def _paper(arxiv_id: str, categories: list[str], published: date) -> Paper:
    return Paper(
        arxiv_id=arxiv_id, title=f"title {arxiv_id}", authors=["A. Author"], abstract="abstract",
        categories=categories, published=published, corpus="evalv1", raw_text="text",
        sections=[], page_count=10,
    )


class TestSqlMetadata:
    def test_a_year_count_is_answered_from_metadata(self, session):
        # g020, which A2 got wrong: the answer is in Postgres, not in any chunk
        answer = sql_metadata(session, "How many papers in the corpus were published in 2026?", "evalv1")

        assert answer.value == 2
        assert "2" in answer.text

    def test_a_corpus_total_is_answered_from_metadata(self, session):
        answer = sql_metadata(session, "How many papers are in the corpus?", "evalv1")

        assert answer.value == 3

    def test_the_most_frequent_category_is_answered_with_its_count(self, session):
        # g038, which A2 abstained on
        answer = sql_metadata(session, "Which arXiv category appears most often across the corpus?", "evalv1")

        assert answer.value == ("cs.AI", 2)
        assert "cs.AI" in answer.text

    def test_a_question_no_rule_matches_returns_nothing(self, session):
        # falling through to retrieval beats inventing an aggregate
        assert sql_metadata(session, "How many rollouts does the GRPO stage generate?", "evalv1") is None

    def test_counting_inside_one_paper_is_not_a_corpus_aggregate(self, session):
        assert sql_metadata(session, "How many CT scans does the Merlin split contain?", "evalv1") is None

    def test_every_answer_names_the_corpus_it_counted(self, session):
        answer = sql_metadata(session, "How many papers are in the corpus?", "evalv1")

        assert "evalv1" in answer.source


class TestSearchPapers:
    def test_hits_come_back_as_plain_records(self):
        hit = FusedHit(
            doc_id="2607.27136::0", arxiv_id="2607.27136", score=0.9, text="passage",
            channels=("bm25",), section_title="Method", page_start=3, page_end=4,
        )

        results = search_papers("q", lambda question: [hit])

        assert results == [
            {
                "doc_id": "2607.27136::0", "arxiv_id": "2607.27136", "score": 0.9,
                "section_title": "Method", "pages": "3-4", "text": "passage",
            }
        ]

    def test_the_question_reaches_the_search_callable(self):
        seen: list[str] = []

        search_papers("the question", lambda question: seen.append(question) or [])

        assert seen == ["the question"]

    def test_a_single_page_hit_reports_one_page(self):
        hit = FusedHit(
            doc_id="d", arxiv_id="a", score=0.1, text="t", channels=("bm25",), page_start=7, page_end=7
        )

        assert search_papers("q", lambda question: [hit])[0]["pages"] == "7"

    def test_a_hit_with_no_page_provenance_reports_none(self):
        hit = FusedHit(doc_id="d", arxiv_id="a", score=0.1, text="t", channels=("bm25",))

        assert search_papers("q", lambda question: [hit])[0]["pages"] is None


class TestIngestByIdRequiresConfirmation:
    """Ingestion spends money and mutates the corpus. No query path may reach it
    on its own, so the tool refuses without an explicit confirmation."""

    def test_without_confirmation_it_refuses_and_runs_nothing(self):
        def must_not_run(*args, **kwargs):
            raise AssertionError("ingestion ran without confirmation")

        with pytest.raises(ConfirmationRequired):
            ingest_by_id("2601.00001", "evalv1", stages=must_not_run, confirm=False)

    def test_the_refusal_names_the_paper_it_declined_to_ingest(self):
        with pytest.raises(ConfirmationRequired, match="2601.00001"):
            ingest_by_id("2601.00001", "evalv1", stages=lambda *a, **k: {}, confirm=False)

    def test_with_confirmation_the_stages_run_and_their_report_comes_back(self):
        def stages(arxiv_id: str, corpus: str) -> dict:
            return {"arxiv_id": arxiv_id, "corpus": corpus, "chunks": 42}

        assert ingest_by_id("2601.00001", "evalv1", stages=stages, confirm=True)["chunks"] == 42


class TestDispatch:
    def test_a_computable_question_is_offered_to_metadata_first(self, session):
        tool = dispatch("computable")

        assert tool == "sql_metadata"

    @pytest.mark.parametrize("route", ["semantic", "entity_anchored"])
    def test_retrieval_routes_dispatch_to_search(self, route):
        assert dispatch(route) == "search_papers"

    def test_an_out_of_domain_question_dispatches_to_no_tool(self):
        # the guardrail already answered it; running a tool would spend money
        assert dispatch("out_of_domain") is None
