"""Retrieval metrics for the golden set.

Relevance is computed, not pinned: any chunk containing the evidence quote
counts. Pinning one chunk id would score a correct retrieval as a miss
whenever chunk overlap puts the same quote in two chunks, and would rot the
moment chunking changes.
"""

import math
from typing import NamedTuple

from rapidfuzz import fuzz

from evals.solvability import quote_in_text
from retrieval.schemas import FusedHit, RetrievalHit
from textnorm import normalize


class ChannelScore(NamedTuple):
    recall: float | None
    ndcg: float | None
    retrieved: int


class QuestionScore(NamedTuple):
    per_channel: dict[str, ChannelScore]
    fused: ChannelScore | None
    reachable: bool


def relevant_chunk_ids(quote: str, chunks: list[tuple[str, str]]) -> set[str]:
    return {chunk_id for chunk_id, text in chunks if quote_in_text(quote, text).found}


# A claim is a distilled statement, not a passage: it earns relevance by
# carrying the fact asked for, not by discussing the same subject.
_CLAIM_MATCH_THRESHOLD = 80


def relevant_claim_hashes(
    quote: str, answer: str, claims: list[tuple[str, str]], threshold: int = _CLAIM_MATCH_THRESHOLD
) -> set[str]:
    targets = [normalize(t) for t in (quote, answer) if t]
    relevant = set()
    for claim_hash, claim_text in claims:
        normalized = normalize(claim_text)
        if any(fuzz.token_set_ratio(target, normalized) >= threshold for target in targets):
            relevant.add(claim_hash)
    return relevant


def recall_at_k(ranked_ids: list[str], relevant: set[str], k: int) -> float | None:
    if not relevant:
        return None
    found = relevant & set(ranked_ids[:k])
    return len(found) / len(relevant)


def dcg(ranked_ids: list[str], relevant: set[str]) -> float:
    return sum(1 / math.log2(rank + 2) for rank, doc_id in enumerate(ranked_ids) if doc_id in relevant)


def ndcg_at_k(ranked_ids: list[str], relevant: set[str], k: int) -> float | None:
    if not relevant:
        return None
    ideal = dcg(list(relevant)[:k], relevant)
    return dcg(ranked_ids[:k], relevant) / ideal if ideal else 0.0


def _score(ranked_ids: list[str], relevant: set[str], k: int) -> ChannelScore:
    return ChannelScore(
        recall=recall_at_k(ranked_ids, relevant, k),
        ndcg=ndcg_at_k(ranked_ids, relevant, k),
        retrieved=len(ranked_ids),
    )


def score_question(
    hits_by_channel: dict[str, list[RetrievalHit]],
    fused: list[FusedHit],
    relevant: set[str],
    k: int,
) -> QuestionScore:
    per_channel = {name: _score([h.doc_id for h in hits], relevant, k) for name, hits in hits_by_channel.items()}
    # Reachability is the ceiling reranking cannot raise: a chunk no channel
    # returned is lost before the reranker ever sees the shortlist.
    retrieved_anywhere = {h.doc_id for hits in hits_by_channel.values() for h in hits}
    return QuestionScore(
        per_channel=per_channel,
        fused=_score([h.doc_id for h in fused], relevant, k),
        reachable=bool(relevant & retrieved_anywhere),
    )
