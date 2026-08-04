import math
from typing import Any

from retrieval.schemas import RetrievalHit
from search.indices import entities_index_name
from textnorm import normalize


def search_entities(client: Any, corpus: str, query: str, size: int, damping: float = 1.0) -> list[RetrievalHit]:
    body = _build_query(normalize(query), query.strip(), size)
    response = client.search(index=entities_index_name(corpus), body=body)
    hits = [hit for entity in response["hits"]["hits"] for hit in _expand(entity, damping)]
    return sorted(hits, key=lambda hit: hit.score, reverse=True)[:size]


def _build_query(normalized: str, raw: str, size: int) -> dict:
    # entity_key is normalized at ingest, surface_forms keep their original casing — probe both.
    surface_terms = [normalized] if raw == normalized else [normalized, raw]
    return {
        "size": size,
        "query": {
            "bool": {
                "should": [
                    {"term": {"entity_key": normalized}},
                    {"terms": {"surface_forms": surface_terms}},
                ],
                "minimum_should_match": 1,
            }
        },
    }


def _expand(entity: dict, damping: float) -> list[RetrievalHit]:
    source = entity["_source"]
    score = _damped(entity["_score"], source.get("link_count", 0), damping)
    surface_forms = source.get("surface_forms") or [source["entity_key"]]
    linked_arxiv_ids = source.get("linked_arxiv_ids") or []
    return [
        RetrievalHit(
            doc_id=chunk_id,
            arxiv_id=_arxiv_id_of(chunk_id, linked_arxiv_ids),
            channel="entities",
            score=score,
            text=surface_forms[0],
        )
        for chunk_id in source.get("linked_chunk_ids") or []
    ]


def _damped(base_score: float, link_count: int, damping: float) -> float:
    # An entity every paper mentions is weak evidence; one only a few mention pins the answer.
    return base_score / (1 + damping * math.log(1 + link_count))


def _arxiv_id_of(chunk_id: str, linked_arxiv_ids: list[str]) -> str:
    prefix, separator, _ = chunk_id.partition("::")
    if separator:
        return prefix
    return linked_arxiv_ids[0] if len(linked_arxiv_ids) == 1 else ""
