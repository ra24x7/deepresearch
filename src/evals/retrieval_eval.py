"""Retrieval metrics for the golden set.

Relevance is computed, not pinned: any chunk containing the evidence quote
counts. Pinning one chunk id would score a correct retrieval as a miss
whenever chunk overlap puts the same quote in two chunks, and would rot the
moment chunking changes.
"""

import math
from typing import NamedTuple

from evals.solvability import quote_in_text
from retrieval.schemas import FusedHit, RetrievalHit


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
