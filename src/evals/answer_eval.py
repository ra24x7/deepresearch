"""Scoring for the end-to-end answer eval.

A verdict alone does not say whether the system behaved correctly. On an
`unanswerable` or `out_of_domain` question, declining IS the correct behaviour
(judge rubric v2, rule 4); on every other type abstaining is a miss, scored
apart from WRONG so over-abstention and hallucination stay distinguishable
(rule 5).

**Abstention is decided structurally, not by the judge.** The generator emits an
exact sentinel and the guardrail sets the same one, so whether the system
declined is a string comparison rather than a model's opinion. This matters
because the judge does not reliably use the ABSTAINED label on these types: on
2026-08-17 it returned CORRECT for a textbook abstention while citing rule 4 in
its reason. That path was never calibrated — Phase 1's 29 pairs were all
answerable questions with a uniformly abstaining baseline, so abstention on an
unanswerable question never appeared. Reading the flag instead of the label
avoids changing the judge prompt, which would bump the rubric version and
invalidate every verdict recorded under v2.
"""

from llm.bedrock import Usage
from llm.cost import CostLedger

# The two types where declining to answer is the correct behaviour.
ABSTAIN_IS_CORRECT = frozenset({"unanswerable", "out_of_domain"})


def accumulate_cost(
    ledger: CostLedger,
    *,
    generation_usage: Usage,
    generation_model: str,
    judge_usage: Usage,
    judge_model: str,
    rerank_documents: int,
    embed_calls: int = 1,
) -> CostLedger:
    """Fold one question's spend onto a running total.

    Lives here, not in the driver, because the first version of this lived in
    the driver and silently rebased the running total on each question's own
    graph ledger — so a 150-question run reported the cost of its last question.
    A function that takes the running total as an argument can be tested for
    accumulation; four lines inline in a loop cannot.
    """
    ledger = ledger.add(generation_usage, generation_model)
    ledger = ledger.add(judge_usage, judge_model)
    ledger = ledger.add_embed(calls=embed_calls)
    if rerank_documents:
        ledger = ledger.add_rerank(documents=rerank_documents)
    return ledger


def is_pass(question_type: str, verdict: str, abstained: bool) -> bool:
    if question_type in ABSTAIN_IS_CORRECT:
        return abstained
    return verdict == "CORRECT"
