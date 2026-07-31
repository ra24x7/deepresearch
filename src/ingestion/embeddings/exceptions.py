class EmbeddingInvocationError(Exception):
    """Raised when an embedding provider's API call fails."""


class UnknownEmbeddingProviderError(Exception):
    """Raised when EmbeddingSettings.provider does not match a known provider."""


class MissingEmbeddingClientError(Exception):
    """Raised when a provider that requires an injected client is not given one."""
