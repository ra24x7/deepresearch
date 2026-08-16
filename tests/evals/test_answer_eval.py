import pytest

from evals.answer_eval import ABSTAIN_IS_CORRECT, is_pass

ANSWERABLE_TYPES = [
    "factual_single",
    "entity_anchored",
    "computable",
    "multi_paper",
    "negation",
    "definitional",
]


class TestAnswerableQuestions:
    @pytest.mark.parametrize("question_type", ANSWERABLE_TYPES)
    def test_only_correct_passes(self, question_type):
        assert is_pass(question_type, "CORRECT") is True
        assert is_pass(question_type, "WRONG") is False

    @pytest.mark.parametrize("question_type", ANSWERABLE_TYPES)
    def test_abstaining_on_an_answerable_question_is_a_miss(self, question_type):
        # rubric rule 5 — scored apart from WRONG so over-abstention and
        # hallucination stay distinguishable
        assert is_pass(question_type, "ABSTAINED") is False


class TestAbstentionTypes:
    @pytest.mark.parametrize("question_type", sorted(ABSTAIN_IS_CORRECT))
    def test_abstaining_is_the_pass(self, question_type):
        assert is_pass(question_type, "ABSTAINED") is True

    @pytest.mark.parametrize("question_type", sorted(ABSTAIN_IS_CORRECT))
    def test_a_substantive_answer_is_a_bluff_even_when_the_judge_says_correct(self, question_type):
        # the trap this guards: CORRECT on an unanswerable question means the
        # system produced content it could not have grounded (rubric rule 4)
        assert is_pass(question_type, "CORRECT") is False
        assert is_pass(question_type, "WRONG") is False


class TestTypeCoverage:
    def test_the_two_abstention_types_are_the_ones_the_golden_set_uses(self):
        assert ABSTAIN_IS_CORRECT == {"unanswerable", "out_of_domain"}
