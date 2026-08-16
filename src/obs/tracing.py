"""LLM tracing, and a no-op that stands in when it is not configured.

Langfuse owns the LLM half of observability (traces, generations, scores, eval
datasets); Logfire will own infra spans and node timing (ADR 0006). Cost is
**not** recomputed here — `CostLedger` stays the single source of truth and its
figure is passed through, so the trace and the eval report can never disagree.

Without credentials this degrades to `NullTracer`, matching `IdentityReranker`
and `FakeEmbeddingProvider`: no part of the test suite or an offline eval run
may require an account.
"""

import os
from typing import Any, Protocol, runtime_checkable

from llm.bedrock import Usage

_PUBLIC_KEY_ENV = "LANGFUSE_PUBLIC_KEY"
_SECRET_KEY_ENV = "LANGFUSE_SECRET_KEY"


@runtime_checkable
class Tracer(Protocol):
    enabled: bool

    def generation(
        self, *, name: str, model: str, prompt: str, output: str, usage: Usage, cost_usd: float
    ) -> None: ...

    def flush(self) -> None: ...


class NullTracer:
    enabled = False

    def generation(
        self, *, name: str, model: str, prompt: str, output: str, usage: Usage, cost_usd: float
    ) -> None:
        return None

    def flush(self) -> None:
        return None


class LangfuseTracer:
    enabled = True

    def __init__(self, client: Any) -> None:
        self._client = client

    def generation(
        self, *, name: str, model: str, prompt: str, output: str, usage: Usage, cost_usd: float
    ) -> None:
        self._client.create_generation(
            name=name,
            model=model,
            input=prompt,
            output=output,
            usage_details={"input": usage.input_tokens, "output": usage.output_tokens},
            cost_details={"total": cost_usd},
        )

    def flush(self) -> None:
        self._client.flush()


def build_tracer() -> Tracer:
    if not (os.environ.get(_PUBLIC_KEY_ENV) and os.environ.get(_SECRET_KEY_ENV)):
        return NullTracer()

    from langfuse import Langfuse

    return LangfuseTracer(Langfuse())
