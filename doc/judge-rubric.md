# Judge Rubric — v2

> This rubric is part of the system. Reported accuracy is a function of
> dataset + system + judge prompt, so every change here bumps the version
> and re-runs calibration (see notebooks/phase1_eval_harness/).

## Verdicts

The judge returns exactly one verdict per (question, answer, evidence) triple:

- `CORRECT` — the answer matches the reference on substance
- `WRONG` — the answer contradicts the reference or fabricates
- `ABSTAINED` — the system declined to answer

## Scoring rules

1. **Paraphrase equivalence.** Wording differences don't matter; substance
   does. "Rank 8" and "r=8" are the same answer.
2. **Numeric tolerance.** Exact figures must match. Rounded figures are
   CORRECT if consistent with the reference at the stated precision.
3. **Partial credit is not a verdict.** Multi-part questions: CORRECT only if
   all required parts are answered; a correct-but-incomplete answer is WRONG,
   with the missing part named in the explanation.
4. **Abstention is correct on unanswerable questions.** For questions labeled
   `unanswerable`, ABSTAINED = pass, any substantive answer = fail (bluffing).
5. **Abstention is wrong on answerable questions.** ABSTAINED on an
   answerable question is a miss — scored separately from WRONG so
   over-abstention and hallucination are distinguishable.
6. **Citations must support, not decorate.** If the answer cites a source,
   the cited evidence must actually contain the claim. A correct answer with
   a fabricated citation is WRONG.
7. **Explanation required.** Every verdict includes a one-sentence reason
   naming the deciding rule.
8. **Mathematical equivalence.** A formula is CORRECT if mathematically
   equivalent to the reference regardless of notation — symbolic vs verbal
   ("Σ count(k,T)·|k|" vs "sum of each keyword's frequency times its
   character length"), renamed variables, or reordered commutative terms.
   Any difference that changes the mathematics (missing term, wrong
   operation, wrong constant) is WRONG.

## Revisit conditions

- **Rule 3 (no partial credit):** if Phase 1 calibration shows this rule
  producing verdicts the human labeler finds unfair on multi-part questions,
  consider nugget decomposition for v3 — reference answers split into atomic
  nuggets labeled vital/okay, scored as vital-nugget recall (pattern from
  APS-RAG, arXiv 2607.24663). Trade-off: more authoring work per entry and a
  per-nugget judge task.

## Changelog

| Version | Date | Change |
|---|---|---|
| v1 | 2026-07-28 | Initial rubric, pre-calibration |
| v2 | 2026-07-29 | Rule 8: mathematical equivalence for formula answers |
