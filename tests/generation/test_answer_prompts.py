from generation.prompts import ABSTENTION_SENTINEL, build_answer_prompt
from retrieval.schemas import FusedHit


def _hit(doc_id: str, arxiv_id: str, text: str, section_title: str = "Abstract", page: int | None = 1) -> FusedHit:
    return FusedHit(
        doc_id=doc_id,
        arxiv_id=arxiv_id,
        score=1.0,
        text=text,
        channels=("bm25",),
        section_title=section_title,
        page_start=page,
        page_end=page,
    )


class TestPassages:
    def test_every_passage_reaches_the_prompt(self):
        hits = [_hit("a::0", "2607.27136", "first passage"), _hit("b::0", "2607.26470", "second passage")]

        prompt = build_answer_prompt("what fails?", hits, max_chars=10_000)

        assert "first passage" in prompt
        assert "second passage" in prompt

    def test_each_passage_is_labelled_with_paper_and_section_so_the_answer_can_cite(self):
        hits = [_hit("a::0", "2607.27136", "body", section_title="4.4 Cost Ablation", page=7)]

        prompt = build_answer_prompt("q", hits, max_chars=10_000)

        assert "2607.27136" in prompt
        assert "4.4 Cost Ablation" in prompt
        assert "p7" in prompt

    def test_passages_are_truncated_to_the_character_budget(self):
        hits = [_hit(f"c{i}::0", "2607.27136", "x" * 500) for i in range(20)]

        prompt = build_answer_prompt("q", hits, max_chars=1_000)

        # the budget bounds the passage block, not the whole prompt: the
        # instructions must survive truncation or the model loses its rules
        assert len(prompt) < 3_000
        assert ABSTENTION_SENTINEL in prompt


class TestQuestion:
    def test_the_question_reaches_the_prompt(self):
        prompt = build_answer_prompt("how do the benchmarks fold in cost?", [], max_chars=10_000)

        assert "how do the benchmarks fold in cost?" in prompt


class TestAbstention:
    def test_the_prompt_tells_the_model_how_to_abstain(self):
        prompt = build_answer_prompt("q", [_hit("a::0", "2607.27136", "body")], max_chars=10_000)

        assert ABSTENTION_SENTINEL in prompt

    def test_no_passages_still_produces_a_prompt(self):
        # the guardrail may route a question here with nothing retrieved; the
        # model must still be told to abstain rather than answer from memory
        prompt = build_answer_prompt("q", [], max_chars=10_000)

        assert ABSTENTION_SENTINEL in prompt
        assert "q" in prompt
