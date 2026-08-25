import pytest

from config import GenerationSettings
from generation.escape_hatch import grade_retrieval, rewrite_question
from llm.bedrock import Usage
from retrieval.schemas import FusedHit

SETTINGS = GenerationSettings()
USAGE = Usage(input_tokens=800, output_tokens=20)


def _hit(text: str = "passage text") -> FusedHit:
    return FusedHit(
        doc_id="2607.27136::0", arxiv_id="2607.27136", score=0.4, text=text, channels=("bm25",)
    )


def _json_llm(payload, usage: Usage = USAGE):
    def invoke_json(prompt: str):
        invoke_json.prompt = prompt
        return payload, usage

    return invoke_json


def _text_llm(text: str, usage: Usage = USAGE):
    def invoke(prompt: str):
        invoke.prompt = prompt
        return text, usage

    return invoke


class TestGradeRetrieval:
    def test_a_sufficient_verdict_is_reported_with_its_usage(self):
        grade = grade_retrieval(
            "what is A-RAG?", [_hit()], _json_llm({"sufficient": True, "reason": "covers it"}), SETTINGS
        )

        assert grade.sufficient is True
        assert grade.reason == "covers it"
        assert grade.usage == USAGE

    def test_an_insufficient_verdict_is_reported(self):
        grade = grade_retrieval(
            "what is A-RAG?", [_hit()], _json_llm({"sufficient": False, "reason": "off topic"}), SETTINGS
        )

        assert grade.sufficient is False

    def test_the_passages_and_the_question_both_reach_the_prompt(self):
        llm = _json_llm({"sufficient": True, "reason": ""})

        grade_retrieval("what is A-RAG?", [_hit("the distinctive passage")], llm, SETTINGS)

        assert "what is A-RAG?" in llm.prompt
        assert "the distinctive passage" in llm.prompt

    def test_a_malformed_verdict_fails_open(self):
        # The hatch is an optimisation. A grade we cannot read must not be the
        # reason a query pays for a rewrite and a second retrieval.
        grade = grade_retrieval("q", [_hit()], _json_llm({"unexpected": "shape"}), SETTINGS)

        assert grade.sufficient is True

    def test_no_hits_is_graded_insufficient_without_calling_the_model(self):
        def must_not_be_called(prompt: str):
            raise AssertionError("graded an empty candidate set")

        grade = grade_retrieval("q", [], must_not_be_called, SETTINGS)

        assert grade.sufficient is False
        assert grade.usage == Usage(input_tokens=0, output_tokens=0)


class TestRewriteQuestion:
    def test_the_rewritten_question_is_returned_with_its_usage(self):
        result = rewrite_question("what is A-RAG?", [_hit()], _text_llm("What does A-RAG stand for?"), SETTINGS)

        assert result.question == "What does A-RAG stand for?"
        assert result.usage == USAGE

    def test_surrounding_whitespace_and_quotes_are_stripped(self):
        result = rewrite_question("q", [_hit()], _text_llm('  "A better question?"  '), SETTINGS)

        assert result.question == "A better question?"

    @pytest.mark.parametrize("reply", ["", "   ", '""'])
    def test_an_empty_rewrite_falls_back_to_the_original_question(self, reply):
        result = rewrite_question("the original question?", [_hit()], _text_llm(reply), SETTINGS)

        assert result.question == "the original question?"

    def test_the_original_question_reaches_the_prompt(self):
        llm = _text_llm("rewritten")

        rewrite_question("the original question?", [], llm, SETTINGS)

        assert "the original question?" in llm.prompt
