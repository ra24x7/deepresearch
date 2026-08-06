import math
import re
from typing import Any

from retrieval.schemas import RetrievalHit
from search.indices import entities_index_name
from textnorm import normalize

# Entity keys are short phrases, so candidates are query n-grams up to this length.
_MAX_NGRAM = 4
_MAX_CANDIDATES = 400
_TRIM_EDGES = re.compile(r"^[^a-z0-9]+|[^a-z0-9]+$")


def search_entities(client: Any, corpus: str, query: str, size: int, damping: float = 1.0) -> list[RetrievalHit]:
    body = _build_query(_candidate_mentions(query), size)
    response = client.search(index=entities_index_name(corpus), body=body)
    hits = [hit for entity in response["hits"]["hits"] for hit in _expand(entity, damping)]
    return sorted(hits, key=lambda hit: hit.score, reverse=True)[:size]


def _candidate_mentions(query: str, max_ngram: int = _MAX_NGRAM) -> list[str]:
    """Every n-gram of the query, as a candidate entity key.

    A whole question never equals an entity key, so probing the query string
    itself matched nothing. Entity keys are normalized at ingest, so normalized
    n-grams compare directly.
    """
    tokens = [t for t in (_TRIM_EDGES.sub("", w) for w in normalize(query).split()) if t]
    grams = {
        " ".join(tokens[start : start + n])
        for n in range(1, max_ngram + 1)
        for start in range(len(tokens) - n + 1)
    }
    return sorted(grams)[:_MAX_CANDIDATES]


def _build_query(candidates: list[str], size: int) -> dict:
    return {
        "size": size,
        "query": {"bool": {"should": [{"terms": {"entity_key": candidates}}], "minimum_should_match": 1}},
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
