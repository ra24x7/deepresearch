from typing import Any

from retrieval.channels.hits import chunk_hit
from retrieval.schemas import RetrievalHit
from search.indices import chunks_index_name


def search_bm25(client: Any, corpus: str, query: str, size: int) -> list[RetrievalHit]:
    response = client.search(
        index=chunks_index_name(corpus),
        body={"size": size, "query": {"match": {"text": query}}},
    )
    return [chunk_hit(hit, "bm25") for hit in response["hits"]["hits"]]
