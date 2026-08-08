from typing import Any

from retrieval.channels.response import hits_of
from retrieval.schemas import RetrievalHit
from search.indices import chunks_index_name


def search_bm25(client: Any, corpus: str, query: str, size: int) -> list[RetrievalHit]:
    index_name = chunks_index_name(corpus)
    response = client.search(index=index_name, body={"size": size, "query": {"match": {"text": query}}})
    return [_to_hit(hit) for hit in hits_of(response, index_name)]


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
