from typing import NamedTuple

from rapidfuzz import fuzz

from textnorm import normalize

__all__ = ["AuditResult", "QuoteMatch", "audit_quote", "normalize", "quote_in_text"]

# A text meaningfully shorter than the quote cannot wholly contain it; without this
# guard partial_ratio scores a half-quote chunk 100 by sliding it over the quote.
_MIN_TEXT_LENGTH_RATIO = 0.9


class QuoteMatch(NamedTuple):
    found: bool
    match: str


class AuditResult(NamedTuple):
    stage_a: QuoteMatch
    stage_b_found: bool
    stage_b_match: str
    stage_b_chunk_id: str | None


def quote_in_text(quote: str, text: str, threshold: int = 95) -> QuoteMatch:
    normalized_quote = normalize(quote)
    normalized_text = normalize(text)

    if normalized_quote in normalized_text:
        return QuoteMatch(found=True, match="exact")
    # PDF extraction inserts spaces around math/code tokens ("47 . 4", "edge _ search");
    # whitespace-stripped containment is still an exact content match.
    if normalized_quote.replace(" ", "") in normalized_text.replace(" ", ""):
        return QuoteMatch(found=True, match="exact")
    if len(normalized_text) < _MIN_TEXT_LENGTH_RATIO * len(normalized_quote):
        return QuoteMatch(found=False, match="none")
    if fuzz.partial_ratio(normalized_quote, normalized_text) >= threshold:
        return QuoteMatch(found=True, match="fuzzy")
    return QuoteMatch(found=False, match="none")


def audit_quote(
    quote: str, raw_text: str, chunk_texts: list[tuple[str, str]], threshold: int = 95
) -> AuditResult:
    stage_a = quote_in_text(quote, raw_text, threshold)

    fuzzy_chunk_id: str | None = None
    for chunk_id, text in chunk_texts:
        match = quote_in_text(quote, text, threshold)
        if match.match == "exact":
            return AuditResult(stage_a=stage_a, stage_b_found=True, stage_b_match="exact", stage_b_chunk_id=chunk_id)
        if match.match == "fuzzy" and fuzzy_chunk_id is None:
            fuzzy_chunk_id = chunk_id

    if fuzzy_chunk_id is not None:
        return AuditResult(stage_a=stage_a, stage_b_found=True, stage_b_match="fuzzy", stage_b_chunk_id=fuzzy_chunk_id)
    return AuditResult(stage_a=stage_a, stage_b_found=False, stage_b_match="none", stage_b_chunk_id=None)
