from typing import Any

from retrieval.schemas import RetrievalHit
from search.indices import chunks_index_name


def search_bm25(client: Any, corpus: str, query: str, size: int) -> list[RetrievalHit]:
    response = client.search(
        index=chunks_index_name(corpus),
        body={"size": size, "query": {"match": {"text": query}}},
    )
    return [_to_hit(hit) for hit in response["hits"]["hits"]]


def _to_hit(hit: dict) -> RetrievalHit:
    source = hit["_source"]
    return RetrievalHit(
        doc_id=source["chunk_id"],
        arxiv_id=source["arxiv_id"],
        channel="bm25",
        score=hit["_score"],
        text=source["text"],
        section_title=source.get("section_title") or "",
        page_start=source.get("page_start"),
        page_end=source.get("page_end"),
    )
