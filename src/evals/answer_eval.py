"""Scoring for the end-to-end answer eval.

A verdict alone does not say whether the system behaved correctly: on an
`unanswerable` or `out_of_domain` question, ABSTAINED is the pass and any
substantive answer is a bluff (judge rubric v2, rule 4). On every other type
abstaining is a miss, scored apart from WRONG so over-abstention and
hallucination stay distinguishable (rule 5).
"""

# The two types where declining to answer is the correct behaviour.
ABSTAIN_IS_CORRECT = frozenset({"unanswerable", "out_of_domain"})


def is_pass(question_type: str, verdict: str) -> bool:
    if question_type in ABSTAIN_IS_CORRECT:
        return verdict == "ABSTAINED"
    return verdict == "CORRECT"
