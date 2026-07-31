from pydantic import BaseModel, ConfigDict

from llm.bedrock import Usage

_HAIKU_INPUT_USD_PER_MILLION = 1.00
_HAIKU_OUTPUT_USD_PER_MILLION = 5.00
_TOKENS_PER_MILLION = 1_000_000


class CostLedger(BaseModel):
    model_config = ConfigDict(frozen=True)

    input_tokens: int = 0
    output_tokens: int = 0

    def add(self, usage: Usage) -> "CostLedger":
        return CostLedger(
            input_tokens=self.input_tokens + usage.input_tokens,
            output_tokens=self.output_tokens + usage.output_tokens,
        )

    @property
    def total_usd(self) -> float:
        input_cost = self.input_tokens / _TOKENS_PER_MILLION * _HAIKU_INPUT_USD_PER_MILLION
        output_cost = self.output_tokens / _TOKENS_PER_MILLION * _HAIKU_OUTPUT_USD_PER_MILLION
        return input_cost + output_cost

    def per_paper_usd(self, n_papers: int) -> float:
        if n_papers <= 0:
            raise ValueError("n_papers must be positive")
        return self.total_usd / n_papers
