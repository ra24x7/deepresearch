from collections.abc import Callable, Iterable
from typing import Any

from pydantic import BaseModel, ConfigDict

from config import RetrievalSettings
from retrieval.channels.bm25 import search_bm25
from retrieval.channels.dense import search_dense_chunks, search_dense_claims
from retrieval.channels.entities import search_entities
from retrieval.fusion import fuse
from retrieval.router import route as route_query
from retrieval.schemas import CHANNEL_NAMES, Channel, FusedHit, RetrievalHit, Route


def candidate_pool_size(settings: RetrievalSettings, top_k: int | None = None) -> int:
    """How many candidates coarse retrieval asks each channel for."""
    k = settings.top_k if top_k is None else top_k
    return max(settings.over_fetch_multiplier * k, settings.min_candidates)


def fusion_weights(settings: RetrievalSettings) -> dict[str, float]:
    """Per-channel fusion weights. Evals import this rather than restating it:
    a hardcoded copy measures a system we do not ship."""
    return {"bm25": 1.0, "dense_chunks": 1.0, "dense_claims": 1.0, "entities": settings.entity_weight}


def run_channels(
    query: str,
    corpus: str,
    search_client: Any,
    provider: Any,
    size: int,
    settings: RetrievalSettings,
    channels: Iterable[Channel] = CHANNEL_NAMES,
) -> dict[str, list[RetrievalHit]]:
    """Coarse retrieval fan-out. Only the requested channels are queried, so a
    caller sweeping one channel's parameters does not pay for it twice."""
    runners: dict[str, Callable[[], list[RetrievalHit]]] = {
        "bm25": lambda: search_bm25(search_client, corpus, query, size),
        "dense_chunks": lambda: search_dense_chunks(search_client, corpus, provider, query, size),
        "dense_claims": lambda: search_dense_claims(search_client, corpus, provider, query, size),
        "entities": lambda: search_entities(search_client, corpus, query, size, settings.entity_damping),
    }
    return {name: runners[name]() for name in channels}


class SearchResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    query: str
    route: Route
    hits: tuple[FusedHit, ...]
    channel_counts: dict[str, int]
    candidates_considered: int
    reranker_model: str


def search(
    query: str,
    corpus: str,
    search_client: Any,
    provider: Any,
    reranker: Any,
    settings: RetrievalSettings | None = None,
) -> SearchResult:
    settings = settings or RetrievalSettings()
    routed = route_query(query)

    if routed == "out_of_domain":
        # Rejecting before retrieval is the point of the guardrail: an
        # out-of-domain question should cost nothing.
        return SearchResult(
            query=query,
            route=routed,
            hits=(),
            channel_counts={},
            candidates_considered=0,
            reranker_model=reranker.model_id,
        )

    size = candidate_pool_size(settings)
    hits_by_channel = run_channels(query, corpus, search_client, provider, size, settings)
    fused = fuse(hits_by_channel, weights=fusion_weights(settings), top_k=size)
    hits = reranker.rerank(query, fused, settings.top_k) if fused else []

    return SearchResult(
        query=query,
        route=routed,
        hits=tuple(hits),
        channel_counts={name: len(found) for name, found in hits_by_channel.items()},
        candidates_considered=len(fused),
        reranker_model=reranker.model_id,
    )
