# CLAUDE.md — DeepResearch

Production-grade RAG for academic research, built eval-first. Read
`doc/project-status.md` first — it is the resume file: current phase,
checklists, session log, pending decisions.

## Docs map

- `doc/spec.md` — what the product does; definition of "working"
- `doc/architecture.md` — staged pipeline design + governing principles
- `doc/project-status.md` — living roadmap (update at end of session)
- `doc/judge-rubric.md` — versioned grading rules; bump version on any change
- `doc/adr/` — one file per decision, cite the evidence

## Working conventions (established with the user; do not drop)

- **Ask before any live LLM API call** — state expected call count and rough
  cost ("~N calls to <model>, ~$X — run it?"). Local/file/git work needs no ask.
- **No commit-per-edit** — let changes accumulate; commit at milestones or on
  request.
- **Why-questions get explanations + options, not applied fixes.** Wait for a
  decision before editing.
- **The user is the sole verification authority** for the golden dataset and
  human labels. Never clear a `draft_unverified` status or mark labels
  verified on their behalf.
- Eval-before-feature: no retrieval component gets built before the harness
  that measures it (see spec principles).

## Models (ADR 0001)

Both roles on one Bedrock key (`AWS_BEARER_TOKEN_BEDROCK` in `.env`, region
`ap-south-1`, boto3 `bedrock-runtime` converse API):

- Generation: `global.anthropic.claude-haiku-4-5-20251001-v1:0`
- Judge: `global.anthropic.claude-sonnet-4-6`

Bare `anthropic.*` model ids are rejected on-demand — always use the
`global.` inference-profile form. `OPENAI_API_KEY` is optional; if added,
generation switches to gpt-4o-mini (see ADR 0001).

## Commands

```bash
uv sync                                      # install deps (Python 3.13)
uv run python scripts/test_connections.py    # verify keys + discover models
uv run jupyter notebook                      # phase notebooks
```

## Data

- `data/golden_dataset.jsonl` — golden questions; `status: draft_unverified`
  means not yet human-verified. Evidence `quote` is verbatim; `formula` is a
  linearized transcription (never claim it's verbatim).
- `data/papers/` — source PDFs (gitignored, re-downloadable by arXiv id)
- `notebooks/phase1_eval_harness/` — calibration evidence: baseline answers,
  human labels, judge verdicts. Phase 1 closed at 100% judge agreement,
  baseline 0/29 (see its README conclusions and the caveat about the
  uniform-abstention calibration set).
