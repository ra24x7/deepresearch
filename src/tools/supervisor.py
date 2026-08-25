"""The tools a supervisor may call, and the rule that picks between them.

Dispatch is rule-based, from the route the guardrail already computed. An LLM
supervisor costs a call on every query and cannot be justified before an eval
shows the rules failing -- the same bar that keeps `retrieval/router.py` free of
a model.
"""

import re
from collections.abc import Callable, Sequence

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from retrieval.schemas import FusedHit, Route
from textnorm import normalize
from tools.exceptions import ConfirmationRequired
from tools.metadata import category_counts, count_papers

SearchFn = Callable[[str], Sequence[FusedHit]]
IngestStages = Callable[[str, str], dict]

_TOOL_BY_ROUTE: dict[str, str | None] = {
    "computable": "sql_metadata",
    "semantic": "search_papers",
    "entity_anchored": "search_papers",
    "out_of_domain": None,
}

_CORPUS_SCOPE = re.compile(r"\b(?:corpus|papers|documents|publications|preprints|articles)\b")
_YEAR_COUNT = re.compile(r"how many .*\bpublished (?:in|during) (\d{4})")
_TOTAL_COUNT = re.compile(r"how many (?:papers|documents|publications|preprints|articles)")
_TOP_CATEGORY = re.compile(r"\bcategor(?:y|ies)\b.*\b(?:most|commonest|frequent|often)\b")


class MetadataAnswer(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: object
    text: str
    source: str


def dispatch(route: Route) -> str | None:
    """Which tool a route reaches for. `None` means answer without one."""
    return _TOOL_BY_ROUTE.get(route)


def sql_metadata(session: Session, question: str, corpus: str) -> MetadataAnswer | None:
    """Answer a corpus-level aggregate, or `None` when no rule matches.

    Falling through to retrieval is the right failure: of the seven `computable`
    questions A2 got wrong, only g020 and g038 are corpus aggregates at all. The
    other five are arithmetic over retrieved text, which no metadata query fixes.
    """
    text = normalize(question)
    if not _CORPUS_SCOPE.search(text):
        return None

    year_match = _YEAR_COUNT.search(text)
    if year_match:
        year = int(year_match.group(1))
        count = count_papers(session, corpus, published_year=year)
        return _answer(count, f"{count} papers in the corpus were published in {year}.", corpus)

    if _TOP_CATEGORY.search(text):
        counts = category_counts(session, corpus)
        if not counts:
            return None
        name, papers = counts[0]
        return _answer((name, papers), f"{name} appears most often, in {papers} papers.", corpus)

    if _TOTAL_COUNT.search(text):
        count = count_papers(session, corpus)
        return _answer(count, f"The corpus holds {count} papers.", corpus)

    return None


def search_papers(question: str, search: SearchFn) -> list[dict]:
    """Retrieval, flattened to records a caller can read without pydantic."""
    return [
        {
            "doc_id": hit.doc_id,
            "arxiv_id": hit.arxiv_id,
            "score": hit.score,
            "section_title": hit.section_title,
            "pages": _pages(hit),
            "text": hit.text,
        }
        for hit in search(question)
    ]


def ingest_by_id(arxiv_id: str, corpus: str, stages: IngestStages, confirm: bool = False) -> dict:
    """Ingest one paper. Spends money and writes to the corpus, so it refuses
    unless the caller confirms -- no query path reaches it on its own."""
    if not confirm:
        raise ConfirmationRequired(
            f"ingesting {arxiv_id} into {corpus} costs money and writes to the corpus; "
            "pass confirm=True to proceed"
        )
    return stages(arxiv_id, corpus)


def _answer(value: object, text: str, corpus: str) -> MetadataAnswer:
    return MetadataAnswer(value=value, text=text, source=f"corpus metadata ({corpus})")


def _pages(hit: FusedHit) -> str | None:
    if hit.page_start is None:
        return None
    if hit.page_end is None or hit.page_end == hit.page_start:
        return str(hit.page_start)
    return f"{hit.page_start}-{hit.page_end}"
