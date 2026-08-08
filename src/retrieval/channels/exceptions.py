class SearchResponseError(RuntimeError):
    """Raised when an OpenSearch response does not carry a hits envelope."""
