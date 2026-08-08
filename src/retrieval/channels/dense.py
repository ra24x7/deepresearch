from typing import Any

from ingestion.embeddings.base import EmbeddingProvider
from retrieval.channels.hits import chunk_hit, claim_hit
from retrieval.schemas import RetrievalHit
from search.indices import chunks_index_name, claims_index_name


def search_dense_chunks(
    client: Any, corpus: str, provider: EmbeddingProvider, query: str, size: int
) -> list[RetrievalHit]:
    raw_hits = _knn_search(client, chunks_index_name(corpus), provider, query, size)
    return [chunk_hit(raw, "dense_chunks") for raw in raw_hits]


def search_dense_claims(
    client: Any, corpus: str, provider: EmbeddingProvider, query: str, size: int
) -> list[RetrievalHit]:
    raw_hits = _knn_search(client, claims_index_name(corpus), provider, query, size)
    return [claim_hit(raw) for raw in raw_hits]


def _knn_search(client: Any, index_name: str, provider: EmbeddingProvider, query: str, size: int) -> list[dict]:
    vector = provider.embed_query(query)
    body = {"size": size, "query": {"knn": {"embedding": {"vector": vector, "k": size}}}}
    response = client.search(index=index_name, body=body)
    return response.get("hits", {}).get("hits", [])
