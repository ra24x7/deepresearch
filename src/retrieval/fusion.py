from retrieval.schemas import FusedHit, RetrievalHit


def fuse(
    hits_by_channel: dict[str, list[RetrievalHit]],
    weights: dict[str, float] | None = None,
    k: int = 60,
    gate_channels: tuple[str, ...] = ("dense_chunks",),
    top_k: int = 10,
) -> list[FusedHit]:
    """Reciprocal-rank fusion behind a semantic gate.

    Lexical and entity channels may reorder candidates but may never introduce one
    that no gate channel found (doc/architecture.md, Stage 4).
    """
    channel_weights = weights or {}
    gate = set(gate_channels)

    scores: dict[str, float] = {}
    found_in: dict[str, list[str]] = {}
    first_hits: dict[str, RetrievalHit] = {}
    gate_hits: dict[str, RetrievalHit] = {}

    for channel, hits in hits_by_channel.items():
        weight = channel_weights.get(channel, 1.0)
        for rank, hit in enumerate(hits):
            scores[hit.doc_id] = scores.get(hit.doc_id, 0.0) + weight / (k + rank + 1)
            channels = found_in.setdefault(hit.doc_id, [])
            if channel not in channels:
                channels.append(channel)
            first_hits.setdefault(hit.doc_id, hit)
            if channel in gate:
                gate_hits.setdefault(hit.doc_id, hit)

    fused = [
        _to_fused_hit(doc_id, score, tuple(found_in[doc_id]), gate_hits.get(doc_id) or first_hits[doc_id])
        for doc_id, score in scores.items()
        if not gate or doc_id in gate_hits
    ]

    return sorted(fused, key=lambda hit: hit.score, reverse=True)[:top_k]


def _to_fused_hit(doc_id: str, score: float, channels: tuple[str, ...], source: RetrievalHit) -> FusedHit:
    return FusedHit(
        doc_id=doc_id,
        arxiv_id=source.arxiv_id,
        score=score,
        text=source.text,
        channels=channels,
        section_title=source.section_title,
        page_start=source.page_start,
        page_end=source.page_end,
    )
