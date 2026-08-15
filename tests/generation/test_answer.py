from config import GenerationSettings
from generation.answer import generate_answer
from generation.prompts import ABSTENTION_SENTINEL
from llm.bedrock import Usage
from retrieval.schemas import FusedHit

SETTINGS = GenerationSettings(prompt_max_chars=10_000)


def _hit(text: str = "the passage body") -> FusedHit:
    return FusedHit(
        doc_id="2607.27136::0",
        arxiv_id="2607.27136",
        score=1.0,
        text=text,
        channels=("bm25",),
        section_title="Abstract",
        page_start=1,
        page_end=1,
    )


def _fake_llm(reply: str, seen: list[str] | None = None):
    def invoke(prompt: str) -> tuple[str, Usage]:
        if seen is not None:
            seen.append(prompt)
        return reply, Usage(input_tokens=100, output_tokens=20)

    return invoke


class TestResult:
    def test_returns_the_model_text_and_its_usage(self):
        result = generate_answer("q", [_hit()], _fake_llm("KAMR faults ranking. [2607.27136]"), SETTINGS)

        assert result.text == "KAMR faults ranking. [2607.27136]"
        assert result.usage == Usage(input_tokens=100, output_tokens=20)

    def test_the_llm_receives_the_question_and_the_passages(self):
        seen: list[str] = []

        generate_answer("why does it fail?", [_hit("existing retrievers rank triplets")], _fake_llm("x", seen), SETTINGS)

        assert "why does it fail?" in seen[0]
        assert "existing retrievers rank triplets" in seen[0]


class TestAbstention:
    def test_the_sentinel_is_reported_as_an_abstention(self):
        result = generate_answer("q", [_hit()], _fake_llm(ABSTENTION_SENTINEL), SETTINGS)

        assert result.abstained is True

    def test_surrounding_whitespace_does_not_hide_an_abstention(self):
        result = generate_answer("q", [_hit()], _fake_llm(f"  {ABSTENTION_SENTINEL}\n"), SETTINGS)

        assert result.abstained is True

    def test_a_substantive_answer_is_not_an_abstention(self):
        result = generate_answer("q", [_hit()], _fake_llm("The bottleneck is rule application."), SETTINGS)

        assert result.abstained is False

    def test_no_passages_still_produces_an_answer_object(self):
        # out-of-domain and unanswerable questions arrive here with nothing
        # retrieved; the caller still needs usage back for the cost ledger
        result = generate_answer("q", [], _fake_llm(ABSTENTION_SENTINEL), SETTINGS)

        assert result.abstained is True
        assert result.usage.input_tokens == 100
