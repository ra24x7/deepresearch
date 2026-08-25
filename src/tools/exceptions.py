class ToolError(Exception):
    """Base for every supervisor tool failure."""


class ConfirmationRequired(ToolError):
    """Raised by a tool that spends money or mutates the corpus."""
