# Phase 1 — Evaluation Harness

## The questions this phase answers

1. **Can we trust the judge?** Does the LLM judge, following
   [doc/judge-rubric.md](../../doc/judge-rubric.md), agree with human labels
   on a hand-scored calibration set? Target: ≥90% agreement.
2. **What is the no-retrieval baseline?** How many golden questions does the
   bare LLM answer correctly with zero retrieved context? Every later phase
   is measured against this number.
3. **Is the golden dataset sound?** Are all six question types covered, is
   the difficulty spread real, and are questions famous enough that the LLM
   already knows the answers (in which case they get rewritten toward
   recent/obscure papers)?

## Contents

- `calibration.ipynb` — the experiments. Disposable once conclusions graduate.
- Golden dataset: `data/golden_dataset.jsonl` (repo root)
- Judge rubric: `doc/judge-rubric.md` (version-controlled; part of the system)

## Exit criteria (from project-status.md)

- Harness runs in CI
- Ablation report shows per-question answer delta
- No-retrieval baseline accuracy is a known number

## Conclusions (2026-07-29)

- **Judge–human agreement: 100% over 29 pairs, rubric v2, zero disagreements**
  (`judge_verdicts.json`). Caveat: the calibration set was uniform — all 29
  baseline answers were refusals, so every ground-truth verdict was
  ABSTAINED. This certifies the judge on refusal-vs-answer discrimination
  only; re-calibrate on substantive answers when Phase 3 produces them
  (CORRECT / WRONG / incomplete distinctions are untested).
- **No-retrieval baseline: 0/29 correct — 29/29 clean abstentions.** Zero
  parametric leakage: the all-2026 corpus is fully outside Haiku 4.5's
  training data, and it abstained rather than fabricated on every question.
  Any future RAG accuracy above 0% is attributable to retrieval alone.
- **Dataset:** 33 questions (29 answerable) drawn from four 2026 RAG papers,
  human-verified via draft-and-verify. No questions needed rewriting for
  fame; the recency selection did its job. Formula evidence carries
  linearized transcriptions in a `formula` field (quotes stay verbatim).
- **Rubric:** v2 (added mathematical-equivalence rule 8). Nugget
  decomposition documented as v3 candidate with trigger conditions.
- **Baseline labels:** drafted by the assistant, verified by the human — an
  acceptable shortcut only because the answer set was uniform refusals;
  Phase 3 labels must be human-first.
