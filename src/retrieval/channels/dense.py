from typing import Any

from ingestion.embeddings.base import EmbeddingProvider
from retrieval.schemas import RetrievalHit
from search.indices import chunks_index_name, claims_index_name


def search_dense_chunks(
    client: Any, corpus: str, provider: EmbeddingProvider, query: str, size: int
) -> list[RetrievalHit]:
    raw_hits = _knn_search(client, chunks_index_name(corpus), provider, query, size)
    return [_to_chunk_hit(raw) for raw in raw_hits]


def search_dense_claims(
    client: Any, corpus: str, provider: EmbeddingProvider, query: str, size: int
) -> list[RetrievalHit]:
    raw_hits = _knn_search(client, claims_index_name(corpus), provider, query, size)
    return [_to_claim_hit(raw) for raw in raw_hits]


def _knn_search(client: Any, index_name: str, provider: EmbeddingProvider, query: str, size: int) -> list[dict]:
    vector = provider.embed_query(query)
    body = {"size": size, "query": {"knn": {"embedding": {"vector": vector, "k": size}}}}
    response = client.search(index=index_name, body=body)
    return response.get("hits", {}).get("hits", [])


def _to_chunk_hit(raw: dict) -> RetrievalHit:
    source = raw["_source"]
    return RetrievalHit(
        doc_id=source["chunk_id"],
        arxiv_id=source["arxiv_id"],
        channel="dense_chunks",
        score=raw["_score"],
        text=source["text"],
        section_title=source.get("section_title", ""),
        page_start=source.get("page_start"),
        page_end=source.get("page_end"),
    )


def _to_claim_hit(raw: dict) -> RetrievalHit:
    source = raw["_source"]
    return RetrievalHit(
        doc_id=source["claim_hash"],
        arxiv_id=source["arxiv_id"],
        channel="dense_claims",
        score=raw["_score"],
        text=source["claim_text"],
        section_title=source.get("section_title", ""),
    )
