class ArxivAPIError(Exception):
    """Raised when the arXiv API request fails after retries are exhausted."""


class ArxivNotFoundError(ArxivAPIError):
    """Raised when arXiv returns no metadata entry for a requested id."""


class ArxivParseError(Exception):
    """Raised when the arXiv Atom XML response cannot be parsed."""


class PDFDownloadError(Exception):
    """Raised when a PDF download fails after retries are exhausted."""


class ParserError(Exception):
    """Raised when a PDF cannot be parsed into structured content."""


class PDFTooLargeError(ParserError):
    """Raised when a PDF exceeds the configured page limit."""
