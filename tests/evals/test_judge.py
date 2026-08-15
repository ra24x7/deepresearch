import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from config import JudgeSettings
from evals.judge import Verdict, build_judge_prompt, judge_answer, load_rubric
from llm.bedrock import Usage

SETTINGS = JudgeSettings()
RUBRIC = "RULES GO HERE"
VERDICTS_PATH = Path("notebooks/phase1_eval_harness/judge_verdicts.json")


def _fake_llm(reply: dict, seen: list[str] | None = None):
    def invoke_json(prompt: str) -> tuple[dict, Usage]:
        if seen is not None:
            seen.append(prompt)
        return reply, Usage(input_tokens=500, output_tokens=40)

    return invoke_json


class TestPrompt:
    def test_carries_the_rubric_question_reference_and_candidate(self):
        prompt = build_judge_prompt(
            question="what rank?", answer="r=4", reference="r=4 or 8", evidence=[], rubric=RUBRIC
        )

        assert RUBRIC in prompt
        assert "what rank?" in prompt
        assert "r=4 or 8" in prompt
        assert "r=4" in prompt

    def test_evidence_lists_quotes_before_formulas(self):
        evidence = [{"quote": "the quoted span", "formula": "a + b"}]

        prompt = build_judge_prompt(question="q", answer="a", reference="r", evidence=evidence, rubric=RUBRIC)

        assert prompt.index("the quoted span") < prompt.index("a + b")

    def test_absent_evidence_renders_as_an_explicit_marker(self):
        # unanswerable and out_of_domain entries carry no evidence by design;
        # an empty block would read as "evidence withheld" to the judge
        prompt = build_judge_prompt(question="q", answer="a", reference=None, evidence=[], rubric=RUBRIC)

        assert "(none)" in prompt


class TestVerdict:
    def test_returns_the_verdict_and_reason(self):
        reply = {"verdict": "CORRECT", "reason": "Rule 1: paraphrase equivalence."}

        result = judge_answer("q", "a", "r", [], RUBRIC, _fake_llm(reply), SETTINGS)

        assert result.verdict == "CORRECT"
        assert result.reason == "Rule 1: paraphrase equivalence."

    def test_usage_is_returned_for_the_cost_ledger(self):
        reply = {"verdict": "WRONG", "reason": "Rule 3: incomplete."}

        result = judge_answer("q", "a", "r", [], RUBRIC, _fake_llm(reply), SETTINGS)

        assert result.usage == Usage(input_tokens=500, output_tokens=40)

    def test_a_verdict_outside_the_rubric_is_rejected(self):
        # the rubric defines exactly three verdicts; anything else means the
        # judge drifted and must not be silently recorded as a result
        reply = {"verdict": "PARTIAL", "reason": "half right"}

        with pytest.raises(ValidationError):
            judge_answer("q", "a", "r", [], RUBRIC, _fake_llm(reply), SETTINGS)


class TestPhase1Fixtures:
    def test_every_stored_calibration_verdict_still_parses(self):
        """Guards against tightening validation past what Phase 1 actually produced.

        This proves the parsing and validation layer accepts all 29 recorded
        verdicts — not that the extracted judge reproduces them, which only a
        live re-run could show.
        """
        stored = json.loads(VERDICTS_PATH.read_text())
        assert len(stored) == 29

        for row in stored:
            result = judge_answer("q", "a", "r", [], RUBRIC, _fake_llm(row["judge"]), SETTINGS)
            assert result.verdict == row["judge"]["verdict"]

    def test_the_stored_verdicts_only_use_rubric_values(self):
        stored = json.loads(VERDICTS_PATH.read_text())

        assert {row["judge"]["verdict"] for row in stored} <= {"CORRECT", "WRONG", "ABSTAINED"}


class TestRubricLoading:
    def test_loads_the_versioned_rubric_from_disk(self):
        rubric = load_rubric()

        assert "Judge Rubric" in rubric
        assert "CORRECT" in rubric


class TestVerdictModel:
    def test_is_frozen(self):
        verdict = Verdict(verdict="CORRECT", reason="x", usage=Usage(input_tokens=1, output_tokens=1))

        with pytest.raises(ValidationError):
            verdict.verdict = "WRONG"
