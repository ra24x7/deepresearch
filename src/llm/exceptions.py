class LLMInvocationError(Exception):
    """Raised when a Bedrock converse call fails after retries are exhausted."""


class LLMJSONParseError(Exception):
    """Raised when a model response is not valid JSON after one retry."""
