import re

from retrieval.schemas import Route
from textnorm import normalize

_AGGREGATE_CUES = (
    "how many",
    "how much",
    "how often",
    "number of",
    "count of",
    "total",
    "average",
    "median",
    "earliest",
    "latest",
    "most recent",
    "oldest",
    "newest",
    "list all",
    "published in",
    "published before",
    "published after",
    "published between",
)

_CORPUS_SCOPE_TERMS = ("paper", "document", "corpus", "publication", "preprint", "article", "author")

_OUT_OF_DOMAIN_TERMS = (
    "hello",
    "hi",
    "hey",
    "thanks",
    "thank you",
    "good morning",
    "good evening",
    "how are you",
    "who are you",
    "your name",
    "joke",
    "jokes",
    "weather",
    "recipe",
    "recipes",
    "cook",
    "cooking",
    "bake",
    "baking",
    "pizza",
    "pasta",
    "restaurant",
    "restaurants",
    "movie",
    "movies",
    "song",
    "songs",
    "football",
    "soccer",
    "basketball",
    "stock price",
    "flight",
    "flights",
    "hotel",
    "hotels",
    "horoscope",
    "birthday",
)

_RESEARCH_TERMS = (
    "paper",
    "arxiv",
    "corpus",
    "publication",
    "research",
    "study",
    "author",
    "citation",
    "section",
    "figure",
    "abstract",
    "model",
    "retriev",
    "embed",
    "dataset",
    "benchmark",
    "chunk",
    "index",
    "rerank",
    "evaluat",
    "experiment",
    "ablation",
    "baseline",
    "accuracy",
    "recall",
    "precision",
    "train",
    "fine-tune",
    "llm",
    "rag",
    "algorithm",
    "architecture",
    "formula",
    "token",
    "knowledge graph",
    "method",
)

_ARXIV_ID_PATTERN = re.compile(r"\b\d{4}\.\d{4,5}\b")
_METRIC_AT_K_PATTERN = re.compile(r"\b[a-z][a-z0-9]{0,15}@\d+\b")
_ACRONYM_PATTERN = re.compile(r"[A-Z]{2,}[A-Za-z0-9]*")
_WORD_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*")
_OUT_OF_DOMAIN_PATTERN = re.compile(r"\b(?:" + "|".join(_OUT_OF_DOMAIN_TERMS) + r")\b")
_RESEARCH_PATTERN = re.compile(r"\b(?:" + "|".join(_RESEARCH_TERMS) + r")\w*")


def route(query: str) -> Route:
    """Pick a retrieval strategy from surface cues alone; semantic is the safe default."""
    text = normalize(query)
    if _is_out_of_domain(text):
        return "out_of_domain"
    if _is_corpus_aggregate(text):
        return "computable"
    if _has_entity_anchor(query, text):
        return "entity_anchored"
    return "semantic"


def _is_out_of_domain(text: str) -> bool:
    if _RESEARCH_PATTERN.search(text):
        return False
    return bool(_OUT_OF_DOMAIN_PATTERN.search(text))


def _is_corpus_aggregate(text: str) -> bool:
    has_cue = any(cue in text for cue in _AGGREGATE_CUES)
    has_scope = any(term in text for term in _CORPUS_SCOPE_TERMS)
    return has_cue and has_scope


def _has_entity_anchor(query: str, text: str) -> bool:
    if _ARXIV_ID_PATTERN.search(text) or _METRIC_AT_K_PATTERN.search(text):
        return True
    # A shouted query carries no case signal, so every token would read as an acronym.
    if not any(char.islower() for char in query):
        return False
    return any(_is_artefact_token(token) for token in _WORD_TOKEN_PATTERN.findall(query))


def _is_artefact_token(token: str) -> bool:
    if _ACRONYM_PATTERN.fullmatch(token):
        return True
    parts = token.split("-")
    return len(parts) > 1 and any(_is_artefact_part(part) for part in parts)


def _is_artefact_part(part: str) -> bool:
    if _ACRONYM_PATTERN.fullmatch(part):
        return True
    return any(char.isdigit() for char in part) and any(char.isalpha() for char in part)
