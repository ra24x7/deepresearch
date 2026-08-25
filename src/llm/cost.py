"""Per-model cost accounting.

**The token rates below are Anthropic first-party rates, not verified against
Bedrock.** This project calls Claude through Bedrock, which AWS operates and
prices separately; the two may differ. Reconcile against an AWS bill before
treating any figure derived from here as exact — see doc/eval-log.md.
"""

import math
from typing import NamedTuple

from pydantic import BaseModel, ConfigDict, Field

from llm.bedrock import Usage

HAIKU_4_5 = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
SONNET_4_6 = "global.anthropic.claude-sonnet-4-6"
RERANK_3_5 = "cohere.rerank-v3-5:0"
EMBED_V4 = "global.cohere.embed-v4:0"

_TOKENS_PER_MILLION = 1_000_000

# Anthropic prompt caching: writing the cache costs a quarter more than plain
# input, reading it costs a tenth. Unverified against Bedrock, like the rates
# below.
_CACHE_WRITE_MULTIPLIER = 1.25
_CACHE_READ_MULTIPLIER = 0.10


class ModelRate(NamedTuple):
    input_usd_per_million: float
    output_usd_per_million: float


# Anthropic first-party rates. Unverified against Bedrock — see module docstring.
_TOKEN_RATES: dict[str, ModelRate] = {
    HAIKU_4_5: ModelRate(1.00, 5.00),
    SONNET_4_6: ModelRate(3.00, 15.00),
}

# AWS Bedrock, Cohere section: "$2.00 per 1,000 queries", where one query holds
# up to 100 document chunks and a request of 350 documents bills as 4 queries.
_RERANK_USD_PER_THOUSAND_QUERIES = 2.00
_RERANK_DOCUMENTS_PER_QUERY = 100

# Cohere Embed v4 is not listed on the public Bedrock pricing page, so embed
# usage is counted and reported as unpriced rather than costed at zero.
_UNPRICED_MODELS = frozenset({EMBED_V4})


class TokenTotals(BaseModel):
    model_config = ConfigDict(frozen=True)

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


class CostLedger(BaseModel):
    model_config = ConfigDict(frozen=True)

    tokens_by_model: dict[str, TokenTotals] = Field(default_factory=dict)
    rerank_queries: int = 0
    embed_calls: int = 0

    def add(self, usage: Usage, model_id: str) -> "CostLedger":
        current = self.tokens_by_model.get(model_id, TokenTotals())
        updated = TokenTotals(
            input_tokens=current.input_tokens + usage.input_tokens,
            output_tokens=current.output_tokens + usage.output_tokens,
            cache_read_tokens=current.cache_read_tokens + usage.cache_read_tokens,
            cache_write_tokens=current.cache_write_tokens + usage.cache_write_tokens,
        )
        return self.model_copy(update={"tokens_by_model": {**self.tokens_by_model, model_id: updated}})

    def add_rerank(self, documents: int) -> "CostLedger":
        # A request over the per-query document cap bills as several queries.
        # This is a lower bound: a document above 512 tokens is itself split
        # into several documents, which we cannot count without token counts.
        queries = math.ceil(documents / _RERANK_DOCUMENTS_PER_QUERY) if documents else 0
        return self.model_copy(update={"rerank_queries": self.rerank_queries + queries})

    def add_embed(self, calls: int = 1) -> "CostLedger":
        return self.model_copy(update={"embed_calls": self.embed_calls + calls})

    @property
    def input_tokens(self) -> int:
        return sum(totals.input_tokens for totals in self.tokens_by_model.values())

    @property
    def output_tokens(self) -> int:
        return sum(totals.output_tokens for totals in self.tokens_by_model.values())

    @property
    def cache_read_tokens(self) -> int:
        return sum(totals.cache_read_tokens for totals in self.tokens_by_model.values())

    @property
    def cache_write_tokens(self) -> int:
        return sum(totals.cache_write_tokens for totals in self.tokens_by_model.values())

    @property
    def total_usd(self) -> float:
        tokens = sum(
            _priced(totals, _TOKEN_RATES[model_id])
            for model_id, totals in self.tokens_by_model.items()
            if model_id in _TOKEN_RATES
        )
        rerank = self.rerank_queries / 1_000 * _RERANK_USD_PER_THOUSAND_QUERIES
        return tokens + rerank

    @property
    def unpriced(self) -> tuple[str, ...]:
        """Components this ledger counted but could not cost.

        A caller reporting cost-per-query must surface this: a non-empty tuple
        means the total is a floor, not the whole bill.
        """
        missing = [model_id for model_id in self.tokens_by_model if model_id not in _TOKEN_RATES]
        if self.embed_calls:
            missing.append(EMBED_V4)
        return tuple(missing)

    def per_paper_usd(self, n_papers: int) -> float:
        if n_papers <= 0:
            raise ValueError("n_papers must be positive")
        return self.total_usd / n_papers


def _priced(totals: TokenTotals, rate: ModelRate) -> float:
    cached_input = (
        totals.cache_read_tokens * _CACHE_READ_MULTIPLIER
        + totals.cache_write_tokens * _CACHE_WRITE_MULTIPLIER
    )
    return (
        (totals.input_tokens + cached_input) / _TOKENS_PER_MILLION * rate.input_usd_per_million
        + totals.output_tokens / _TOKENS_PER_MILLION * rate.output_usd_per_million
    )
