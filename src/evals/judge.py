"""LLM-as-judge, lifted out of notebooks/phase1_eval_harness/calibration.ipynb.

The prompt below is reproduced verbatim from the notebook that Phase 1
calibrated at 100% agreement over 29 pairs. Changing its wording changes what
the grades mean, so any edit here bumps the rubric version and re-runs
calibration (see CLAUDE.md, "Change the judge rubric").
"""

from collections.abc import Callable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from config import JudgeSettings
from llm.bedrock import Usage

RUBRIC_PATH = Path("doc/judge-rubric.md")

_NO_EVIDENCE = "(none)"

_PROMPT_TEMPLATE = """You are grading an answer to a research question. Apply these rules exactly:

{rubric}

QUESTION: {question}
REFERENCE ANSWER: {reference}
SUPPORTING EVIDENCE: {evidence}
CANDIDATE ANSWER: {answer}

Respond with only a JSON object: {{"verdict": "CORRECT" | "WRONG" | "ABSTAINED", "reason": "<one sentence naming the deciding rule>"}}"""


class Verdict(BaseModel):
    model_config = ConfigDict(frozen=True)

    verdict: Literal["CORRECT", "WRONG", "ABSTAINED"]
    reason: str
    usage: Usage


def load_rubric(path: Path = RUBRIC_PATH) -> str:
    return path.read_text()


def build_judge_prompt(
    question: str, answer: str, reference: str | None, evidence: list[dict], rubric: str
) -> str:
    return _PROMPT_TEMPLATE.format(
        rubric=rubric,
        question=question,
        reference=reference,
        evidence=_build_evidence(evidence),
        answer=answer,
    )


def judge_answer(
    question: str,
    answer: str,
    reference: str | None,
    evidence: list[dict],
    rubric: str,
    llm_invoke_json: Callable[[str], tuple[dict, Usage]],
    settings: JudgeSettings,
) -> Verdict:
    prompt = build_judge_prompt(question, answer, reference, evidence, rubric)
    data, usage = llm_invoke_json(prompt)
    return Verdict(verdict=data.get("verdict"), reason=data.get("reason", ""), usage=usage)


def _build_evidence(evidence: list[dict]) -> str:
    # quotes first, then formulas — the order Phase 1 calibrated against. A
    # formula is a linearized transcription, never verbatim (CLAUDE.md).
    parts = [e["quote"] for e in evidence if e.get("quote")]
    parts += [e["formula"] for e in evidence if e.get("formula")]
    return "\n".join(parts) or _NO_EVIDENCE
