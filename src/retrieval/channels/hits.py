"""Mapping an OpenSearch hit onto a RetrievalHit.

Chunk-shaped hits come back from two channels (BM25 and dense) with identical
documents and differ only in which channel found them, so the field mapping is
written once — a new field added to the chunks index cannot reach one channel
and silently miss the other.
"""

from retrieval.schemas import Channel, RetrievalHit


def chunk_hit(raw: dict, channel: Channel) -> RetrievalHit:
    source = raw["_source"]
    return RetrievalHit(
        doc_id=source["chunk_id"],
        arxiv_id=source["arxiv_id"],
        channel=channel,
        score=raw["_score"],
        text=source["text"],
        section_title=source.get("section_title") or "",
        page_start=source.get("page_start"),
        page_end=source.get("page_end"),
    )


def claim_hit(raw: dict) -> RetrievalHit:
    source = raw["_source"]
    return RetrievalHit(
        doc_id=source["claim_hash"],
        arxiv_id=source["arxiv_id"],
        channel="dense_claims",
        score=raw["_score"],
        text=source["claim_text"],
        section_title=source.get("section_title") or "",
    )
