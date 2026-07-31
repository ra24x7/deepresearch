import re
import unicodedata

_PUNCTUATION_MAP = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", "−": "-", "‐": "-"})
_LINE_BREAK_HYPHEN = re.compile(r"(\w)-\n(\w)")
_WHITESPACE_RUN = re.compile(r"\s+")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(_PUNCTUATION_MAP)
    text = _LINE_BREAK_HYPHEN.sub(r"\1\2", text)
    text = _WHITESPACE_RUN.sub(" ", text)
    return text.strip().lower()
