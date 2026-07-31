import hashlib
import math
import random

_DEFAULT_DIMENSION = 1024


class FakeEmbeddingProvider:
    """Deterministic, dependency-free embedding provider for tests and pipeline dry-runs."""

    def __init__(self, dimension: int = _DEFAULT_DIMENSION):
        self._dimension = dimension

    @property
    def model_id(self) -> str:
        return "fake"

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        seed = hashlib.sha256(text.encode()).digest()
        rng = random.Random(seed)
        vector = [rng.uniform(-1.0, 1.0) for _ in range(self._dimension)]
        norm = math.sqrt(sum(v * v for v in vector))
        return [v / norm for v in vector]
