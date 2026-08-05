from typing import Protocol, runtime_checkable

from retrieval.schemas import FusedHit


@runtime_checkable
class Reranker(Protocol):
    """Second-stage scorer: reads the query against each candidate.

    Fusion orders by rank agreement across channels and never reads the text;
    a reranker does, which is why it only ever sees an over-fetched shortlist.
    """

    @property
    def model_id(self) -> str: ...

    def rerank(self, query: str, hits: list[FusedHit], top_n: int) -> list[FusedHit]: ...
