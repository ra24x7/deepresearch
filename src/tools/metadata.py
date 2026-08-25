"""Corpus metadata the retriever cannot answer: counts, spreads, per-paper claims.

Every query here is a fixed, parameterized aggregate. No caller supplies SQL --
the `computable` route exists because two golden questions (g020, g038) ask
about the corpus as a whole, not because a model should be writing queries
against this database.
"""

from collections import Counter

from sqlalchemy.orm import Session

from db.models import Claim, Paper


def count_papers(session: Session, corpus: str, published_year: int | None = None) -> int:
    papers = session.query(Paper.published).filter(Paper.corpus == corpus).all()
    if published_year is None:
        return len(papers)
    return sum(1 for (published,) in papers if published.year == published_year)


def papers_by_year(session: Session, corpus: str) -> list[tuple[int, int]]:
    years = Counter(
        published.year for (published,) in session.query(Paper.published).filter(Paper.corpus == corpus)
    )
    return sorted(years.items())


def category_counts(session: Session, corpus: str) -> list[tuple[str, int]]:
    """How many papers carry each arXiv category, most frequent first.

    Counted in Python rather than SQL: `categories` is a JSON array, and
    unnesting it portably costs more than a Counter over a corpus this size.
    Ties break on category name so the answer does not move between runs.
    """
    counts = Counter(
        category
        for (categories,) in session.query(Paper.categories).filter(Paper.corpus == corpus)
        for category in categories
    )
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


def get_claims(session: Session, arxiv_id: str) -> list[dict]:
    claims = session.query(Claim).filter(Claim.arxiv_id == arxiv_id).order_by(Claim.claim_hash).all()
    return [
        {"claim_hash": c.claim_hash, "claim_text": c.claim_text, "section_title": c.section_title}
        for c in claims
    ]
