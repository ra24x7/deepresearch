from typing import Any

from pydantic import BaseModel, ConfigDict

from config import RetrievalSettings
from retrieval.channels.bm25 import search_bm25
from retrieval.channels.dense import search_dense_chunks, search_dense_claims
from retrieval.channels.entities import search_entities
from retrieval.fusion import fuse
from retrieval.router import route as route_query
from retrieval.schemas import FusedHit, Route


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

    size = max(settings.over_fetch_multiplier * settings.top_k, settings.min_candidates)
    hits_by_channel = {
        "bm25": search_bm25(search_client, corpus, query, size),
        "dense_chunks": search_dense_chunks(search_client, corpus, provider, query, size),
        "dense_claims": search_dense_claims(search_client, corpus, provider, query, size),
        "entities": search_entities(search_client, corpus, query, size, settings.entity_damping),
    }

    weights = {"bm25": 1.0, "dense_chunks": 1.0, "dense_claims": 1.0, "entities": settings.entity_weight}
    fused = fuse(hits_by_channel, weights=weights, top_k=size)
    hits = reranker.rerank(query, fused, settings.top_k) if fused else []

    return SearchResult(
        query=query,
        route=routed,
        hits=tuple(hits),
        channel_counts={name: len(found) for name, found in hits_by_channel.items()},
        candidates_considered=len(fused),
        reranker_model=reranker.model_id,
    )
