class RerankInvocationError(RuntimeError):
    """The rerank model call failed."""


class UnknownRerankerError(ValueError):
    """No reranker is registered under that provider name."""


class MissingRerankClientError(ValueError):
    """A hosted reranker was requested without a client to call it with."""
