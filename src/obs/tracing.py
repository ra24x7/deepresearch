"""LLM tracing, and a no-op that stands in when it is not configured.

Langfuse owns the LLM half of observability (traces, generations, scores, eval
datasets); Logfire will own infra spans and node timing (ADR 0006). Cost is
**not** recomputed here — `CostLedger` stays the single source of truth and its
figure is passed through, so the trace and the eval report can never disagree.

Without credentials this degrades to `NullTracer`, matching `IdentityReranker`
and `FakeEmbeddingProvider`: no part of the test suite or an offline eval run
may require an account. It degrades the same way when the client cannot be
built or a write fails: by the time a trace is written the run is already paid
for, so losing the trace is cheap and losing the answer is not.
"""

import logging
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
        try:
            observation = self._client.start_observation(
                name=name,
                as_type="generation",
                input=prompt,
                output=output,
                model=model,
                usage_details=_usage_details(usage),
                # ADR 0006: cost is passed through from CostLedger, never
                # recomputed, so a trace and an eval report cannot disagree.
                cost_details={"total": cost_usd},
            )
            observation.end()
        except Exception as exc:  # noqa: BLE001 — see module docstring
            logging.getLogger(__name__).warning("langfuse trace dropped: %s", exc)

    def flush(self) -> None:
        try:
            self._client.flush()
        except Exception as exc:  # noqa: BLE001 — see module docstring
            logging.getLogger(__name__).warning("langfuse flush failed: %s", exc)


def _usage_details(usage: Usage) -> dict[str, int]:
    details = {"input": usage.input_tokens, "output": usage.output_tokens}
    if usage.cache_read_tokens:
        details["cache_read_input_tokens"] = usage.cache_read_tokens
    if usage.cache_write_tokens:
        details["cache_creation_input_tokens"] = usage.cache_write_tokens
    return details


def build_tracer() -> Tracer:
    if not (os.environ.get(_PUBLIC_KEY_ENV) and os.environ.get(_SECRET_KEY_ENV)):
        return NullTracer()

    import langfuse

    try:
        return LangfuseTracer(langfuse.Langfuse())
    except Exception as exc:  # noqa: BLE001 — see module docstring
        logging.getLogger(__name__).warning("langfuse unavailable, tracing disabled: %s", exc)
        return NullTracer()
