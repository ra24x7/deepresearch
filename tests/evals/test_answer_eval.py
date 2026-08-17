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


class TestCostAccumulation:
    def test_two_questions_sum_rather_than_the_second_replacing_the_first(self):
        # the regression this exists for: the driver rebased the running total
        # on each question's own ledger, so a 150-question run reported the
        # cost of its last question and nothing else
        from llm.bedrock import Usage
        from llm.cost import HAIKU_4_5, SONNET_4_6, CostLedger

        from evals.answer_eval import accumulate_cost

        ledger = CostLedger()
        for _ in range(2):
            ledger = accumulate_cost(
                ledger,
                generation_usage=Usage(input_tokens=1_000_000, output_tokens=0),
                generation_model=HAIKU_4_5,
                judge_usage=Usage(input_tokens=1_000_000, output_tokens=0),
                judge_model=SONNET_4_6,
                rerank_documents=60,
            )

        assert ledger.input_tokens == 4_000_000
        assert ledger.rerank_queries == 2
        assert ledger.embed_calls == 2
        assert ledger.total_usd == pytest.approx(2 * (1.00 + 3.00) + 2 / 1_000 * 2.00)

    def test_an_identity_rerank_run_records_no_rerank_queries(self):
        from llm.bedrock import Usage
        from llm.cost import HAIKU_4_5, SONNET_4_6, CostLedger

        from evals.answer_eval import accumulate_cost

        ledger = accumulate_cost(
            CostLedger(),
            generation_usage=Usage(input_tokens=10, output_tokens=1),
            generation_model=HAIKU_4_5,
            judge_usage=Usage(input_tokens=10, output_tokens=1),
            judge_model=SONNET_4_6,
            rerank_documents=0,
        )

        assert ledger.rerank_queries == 0
