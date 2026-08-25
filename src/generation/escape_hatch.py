"""Grade the retrieved passages, and rewrite the question when they miss.

Fired only when the reranker's confidence in its own top hit is low, so the
happy path pays nothing for it. Both calls are ordinary LLM invocations passed
in as callables, which keeps this testable without a client.
"""

from collections.abc import Callable, Sequence

from pydantic import BaseModel, ConfigDict

from config import GenerationSettings
from generation.prompts import build_grade_prompt, build_rewrite_prompt
from llm.bedrock import Usage
from retrieval.schemas import FusedHit

_NO_USAGE = Usage(input_tokens=0, output_tokens=0)


class RetrievalGrade(BaseModel):
    model_config = ConfigDict(frozen=True)

    sufficient: bool
    reason: str
    usage: Usage


class RewrittenQuestion(BaseModel):
    model_config = ConfigDict(frozen=True)

    question: str
    usage: Usage


def grade_retrieval(
    question: str,
    hits: Sequence[FusedHit],
    llm_invoke_json: Callable[[str], tuple[dict, Usage]],
    settings: GenerationSettings,
) -> RetrievalGrade:
    if not hits:
        return RetrievalGrade(sufficient=False, reason="nothing was retrieved", usage=_NO_USAGE)

    payload, usage = llm_invoke_json(build_grade_prompt(question, hits, settings.prompt_max_chars))
    sufficient = payload.get("sufficient")
    if not isinstance(sufficient, bool):
        # The hatch is an optimisation: an unreadable grade must not be the
        # reason a query pays for a rewrite and a second retrieval.
        return RetrievalGrade(sufficient=True, reason="grade unreadable, failing open", usage=usage)
    return RetrievalGrade(sufficient=sufficient, reason=str(payload.get("reason", "")), usage=usage)


def rewrite_question(
    question: str,
    hits: Sequence[FusedHit],
    llm_invoke: Callable[[str], tuple[str, Usage]],
    settings: GenerationSettings,
) -> RewrittenQuestion:
    text, usage = llm_invoke(build_rewrite_prompt(question, hits, settings.prompt_max_chars))
    rewritten = text.strip().strip('"').strip()
    return RewrittenQuestion(question=rewritten or question, usage=usage)
