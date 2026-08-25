import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from config import JudgeSettings
from evals.judge import (
    Verdict,
    build_judge_body,
    build_judge_prefix,
    build_judge_prompt,
    judge_answer,
    load_rubric,
)
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


class TestRubricCaching:
    """The rubric is ~1.5k tokens re-sent on every question -- 225k of A2's
    1.09M input tokens were 150 copies of one static document. Splitting it out
    as a cached prefix must not change a single character the model receives.
    """

    def test_the_prefix_and_body_concatenate_to_the_uncached_prompt(self):
        prefix = build_judge_prefix(RUBRIC)
        body = build_judge_body(
            question="what rank?", answer="r=4", reference="r=4 or 8", evidence=[]
        )

        assert prefix + body == build_judge_prompt(
            question="what rank?", answer="r=4", reference="r=4 or 8", evidence=[], rubric=RUBRIC
        )

    def test_the_prefix_holds_the_rubric_and_nothing_question_specific(self):
        prefix = build_judge_prefix(RUBRIC)

        assert RUBRIC in prefix
        assert "QUESTION:" not in prefix

    def test_by_default_the_rubric_is_sent_inline_as_one_prompt(self):
        seen: list[str] = []

        judge_answer(
            "q", "a", "r", [], RUBRIC, _fake_llm({"verdict": "CORRECT", "reason": ""}, seen), SETTINGS
        )

        assert RUBRIC in seen[0]

    def test_with_caching_on_the_rubric_travels_as_the_cached_prefix(self):
        calls: list[tuple[str, str | None]] = []

        def invoke_json(prompt: str, cached_prefix: str | None = None):
            calls.append((prompt, cached_prefix))
            return {"verdict": "CORRECT", "reason": ""}, Usage(input_tokens=50, output_tokens=10)

        judge_answer("q", "a", "r", [], RUBRIC, invoke_json, SETTINGS, cache_rubric=True)

        body, prefix = calls[0]
        assert RUBRIC in prefix
        assert RUBRIC not in body

    def test_a_cached_verdict_is_parsed_the_same_way(self):
        def invoke_json(prompt: str, cached_prefix: str | None = None):
            return {"verdict": "WRONG", "reason": "rule 2"}, Usage(input_tokens=50, output_tokens=10)

        verdict = judge_answer("q", "a", "r", [], RUBRIC, invoke_json, SETTINGS, cache_rubric=True)

        assert (verdict.verdict, verdict.reason) == ("WRONG", "rule 2")
