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
  human labels.
- Eval-before-feature: no retrieval component gets built before the harness
  that measures it (see spec principles).

## Do NOT

- Remove a `status: draft_unverified` flag or mark human labels verified —
  only the user does that.
- Use bare `anthropic.*` Bedrock model ids — always the `global.`
  inference-profile form (bare ids are rejected on-demand).
- Make a live LLM API call without stating call count + rough cost and asking.
- Claim an evidence `formula` field is verbatim — it is a linearized
  transcription; only `quote` is verbatim.
- Change the judge prompt or rubric without bumping the rubric version.
- Compare eval numbers across a rubric, generation-model, or dataset change
  without flagging the break in `doc/project-status.md`.
- Build retrieval features before the eval that measures them exists.
- Use pip or conda — this repo is uv-only (Python 3.13).

## Recipes

### Add a golden dataset entry

1. Append one JSON line to `data/golden_dataset.jsonl` with: `id` (next
   `gNNN`), `type` (`factual_single` | `entity_anchored` | `computable` |
   `multi_paper` | `unanswerable` | `out_of_domain`), `question`, `papers`
   (arXiv ids), `evidence` (list of `arxiv_id` / `where` / verbatim `quote`,
   plus `formula` for equations), `expected_behavior`, `reference_answer`,
   and `status: "draft_unverified"`. Add `notes` for traps or context.
2. The status stays until the user verifies the entry and removes it —
   entries without `status` are human-verified.

### Write an ADR

1. Create `doc/adr/NNNN-slug.md` (next number). Header lines: Date, Status,
   Evidence (the run or artifact that grounds the decision). Sections:
   `## Decision`, `## Why` — including known trade-offs accepted.
2. Record it under "Decisions made" in `doc/project-status.md`.

### Change the judge rubric

1. Edit `doc/judge-rubric.md` and bump the version in the title.
2. Re-run calibration against the Phase 1 human labels (this is a live API
   run — ask first) and record the agreement rate.
3. Note the bump and what triggered it in `doc/project-status.md`. Verdicts
   produced under the old version are stale until re-judged.

### Close a phase

1. Write conclusions in the phase notebook's README: what was measured,
   the numbers, and caveats that qualify them.
2. Update `doc/project-status.md`: tick the checklist, add a session-log
   entry, move resolved items out of "Decisions pending".
3. Commit everything as one milestone commit.

## Models (ADR 0001)

Both roles on one Bedrock key (`AWS_BEARER_TOKEN_BEDROCK` in `.env`, region
`ap-south-1`, boto3 `bedrock-runtime` converse API):

- Generation: `global.anthropic.claude-haiku-4-5-20251001-v1:0`
- Judge: `global.anthropic.claude-sonnet-4-6`

`OPENAI_API_KEY` is optional; if added, generation switches to gpt-4o-mini
(see ADR 0001).

## Commands

uv only — never pip or conda (Python 3.13).

```bash
uv sync                                      # install deps
uv run python scripts/test_connections.py    # verify keys + discover models
uv run jupyter notebook                      # phase notebooks
```

## Data

- `data/golden_dataset.jsonl` — golden questions; schema and status flow in
  the recipe above.
- `data/papers/` — source PDFs (gitignored, re-downloadable by arXiv id)
- `notebooks/phase1_eval_harness/` — calibration evidence: baseline answers,
  human labels, judge verdicts. Phase 1 closed at 100% judge agreement,
  baseline 0/29 (see its README conclusions and the caveat about the
  uniform-abstention calibration set).
