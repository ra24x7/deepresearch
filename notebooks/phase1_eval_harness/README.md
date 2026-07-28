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

## Conclusions

> Fill in when experiments complete. Each conclusion cites the notebook
> section that produced it and graduates into an ADR and/or CI test.

- Judge–human agreement: _pending_
- No-retrieval baseline accuracy: _pending_
- Dataset revisions made: _pending_
