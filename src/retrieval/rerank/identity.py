from retrieval.schemas import FusedHit


class IdentityReranker:
    """Keeps fusion's order. Lets the whole read path run without spending."""

    @property
    def model_id(self) -> str:
        return "identity"

    def rerank(self, query: str, hits: list[FusedHit], top_n: int) -> list[FusedHit]:
        return hits[:top_n]
