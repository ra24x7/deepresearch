"""Validation for the identifiers and URLs that cross the arXiv trust boundary.

An arXiv id becomes a filesystem path (`data/papers/<id>.pdf`), a glob pattern
and a database key, so it is validated once, at the edge, rather than trusted
because it came from a response body or a DAG param.
"""

import re
from urllib.parse import urlparse

# Patterns anchor with \Z, not $: `$` also matches before a trailing newline,
# which is exactly the character an injected value hides behind.
# 2501.00001 / 2501.00001v2 — the only form arXiv has minted since 2007.
_MODERN_ID = re.compile(r"\A\d{4}\.\d{4,5}(v\d+)?\Z")
# cs/0703001, math.GT/0309136 — pre-2007 ids, kept accepted for backfills.
_LEGACY_ID = re.compile(r"\A[a-z-]+(\.[A-Z]{2})?/\d{7}(v\d+)?\Z")

_ARXIV_HOSTS = frozenset({"arxiv.org", "www.arxiv.org", "export.arxiv.org"})

_CORPUS_NAME = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
_CATEGORY = re.compile(r"\A[a-z-]+(\.[A-Za-z-]+)?\Z")
_YYYYMMDD = re.compile(r"\A\d{8}\Z")


def validate_arxiv_id(arxiv_id: str) -> str:
    if not isinstance(arxiv_id, str) or not (_MODERN_ID.match(arxiv_id) or _LEGACY_ID.match(arxiv_id)):
        raise ValueError(f"not a well-formed arXiv id: {arxiv_id!r}")
    return arxiv_id


def pdf_filename(arxiv_id: str) -> str:
    # Legacy ids carry a slash, which would resolve to a subdirectory of the
    # PDF cache; the id is already validated, so flattening is enough.
    return f"{validate_arxiv_id(arxiv_id).replace('/', '_')}.pdf"


def validate_pdf_url(pdf_url: str) -> str:
    """Only https URLs on an arXiv host are fetchable — the URL arrives in a response body."""
    if pdf_url == "":
        return pdf_url
    parsed = urlparse(pdf_url)
    if parsed.scheme != "https" or parsed.hostname not in _ARXIV_HOSTS:
        raise ValueError(f"pdf_url must be an https URL on an arXiv host: {pdf_url!r}")
    return pdf_url


def validate_corpus(corpus: str) -> str:
    """A corpus name is interpolated into OpenSearch index names."""
    if not isinstance(corpus, str) or not _CORPUS_NAME.match(corpus):
        raise ValueError(f"corpus must match {_CORPUS_NAME.pattern}: {corpus!r}")
    return corpus


def validate_category(category: str) -> str:
    if not isinstance(category, str) or not _CATEGORY.match(category):
        raise ValueError(f"not a well-formed arXiv category: {category!r}")
    return category


def validate_yyyymmdd(value: str) -> str:
    if not isinstance(value, str) or not _YYYYMMDD.match(value):
        raise ValueError(f"date must be YYYYMMDD: {value!r}")
    return value
