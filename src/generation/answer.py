from collections.abc import Callable, Sequence

from pydantic import BaseModel, ConfigDict

from config import GenerationSettings
from generation.prompts import ABSTENTION_SENTINEL, build_answer_prompt
from llm.bedrock import Usage
from retrieval.schemas import FusedHit


class GeneratedAnswer(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    usage: Usage
    abstained: bool


def generate_answer(
    question: str,
    hits: Sequence[FusedHit],
    llm_invoke: Callable[[str], tuple[str, Usage]],
    settings: GenerationSettings,
) -> GeneratedAnswer:
    prompt = build_answer_prompt(question, hits, settings.prompt_max_chars)
    text, usage = llm_invoke(prompt)
    return GeneratedAnswer(text=text, usage=usage, abstained=text.strip() == ABSTENTION_SENTINEL)
