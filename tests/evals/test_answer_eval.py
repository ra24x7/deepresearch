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
        assert is_pass(question_type, "CORRECT", abstained=False) is True
        assert is_pass(question_type, "WRONG", abstained=False) is False

    @pytest.mark.parametrize("question_type", ANSWERABLE_TYPES)
    def test_abstaining_on_an_answerable_question_is_a_miss(self, question_type):
        # rubric rule 5 — scored apart from WRONG so over-abstention and
        # hallucination stay distinguishable
        assert is_pass(question_type, "ABSTAINED", abstained=True) is False


class TestAbstentionTypes:
    @pytest.mark.parametrize("question_type", sorted(ABSTAIN_IS_CORRECT))
    def test_declining_is_the_pass_whatever_the_judge_labels_it(self, question_type):
        # the judge has been observed returning CORRECT for a textbook
        # abstention while citing rule 4; the structural flag decides here
        assert is_pass(question_type, "ABSTAINED", abstained=True) is True
        assert is_pass(question_type, "CORRECT", abstained=True) is True

    @pytest.mark.parametrize("question_type", sorted(ABSTAIN_IS_CORRECT))
    def test_answering_is_a_bluff_even_when_the_judge_says_correct(self, question_type):
        # the trap this guards: CORRECT on an unanswerable question means the
        # system produced content it could not have grounded (rubric rule 4)
        assert is_pass(question_type, "CORRECT", abstained=False) is False
        assert is_pass(question_type, "WRONG", abstained=False) is False

    @pytest.mark.parametrize("question_type", sorted(ABSTAIN_IS_CORRECT))
    def test_a_refusal_that_keeps_talking_does_not_count_as_declining(self, question_type):
        # observed on g018: the model emitted the sentinel and then described
        # what the passages do contain, so it did not cleanly decline
        assert is_pass(question_type, "CORRECT", abstained=False) is False


class TestTypeCoverage:
    def test_the_two_abstention_types_are_the_ones_the_golden_set_uses(self):
        assert ABSTAIN_IS_CORRECT == {"unanswerable", "out_of_domain"}
