# ADR 0007 — The router anchors on the indexed entity vocabulary, not on shape

Date: 2026-08-25
Status: accepted
Evidence: **D1** (`doc/eval-log.md`, g080 unreachable by every channel); a free
scan of the 150-question golden set against the live `entities` table
(52 of 76 acronym triggers matched a real surface form, 24 matched nothing);
`src/retrieval/router.py`, `src/retrieval/vocabulary.py`

## Decision

**An acronym anchors a query to the entity channel only if the entity index
actually holds it.**

- `route(query, vocabulary)` takes the set of normalised entity surface forms
  and is otherwise unchanged. It stays a pure function: no IO, no client.
- `load_entity_vocabulary(engine)` reads `entity_key` and `surface_forms` from
  Postgres once; the drivers pass the same set to the guardrail and to
  `search()`, so the two cannot disagree about what the entity channel knows.
- arXiv ids and `metric@k` still anchor **without** a vocabulary. Those are
  structurally verifiable and do not depend on what was ingested.
- The default is an empty vocabulary, under which no acronym anchors and the
  query falls through to `semantic` — the safe default the router already
  documents.

## Why

Routing `entity_anchored` is a promise that the entity channel can act on the
query. Nothing was checking that promise.

`_is_artefact_token` accepted any capitalised token of two or more letters, so
**LLM**, **RAG**, **AI**, **QA** and **GPU** all anchored. The entity index
holds none of them: it stores `large language models` and `retrieval-augmented
generation`, because that is what the extractor found in the papers. D1 recorded
the consequence for g080 — the entity channel returns nothing, bm25 returns the
right paper's wrong section — and read it as a defect in the question. It is
also a defect in the router, and this fixes that half.

Measured against the live table, of the acronym triggers on the golden set
**52 occurrences matched a real surface form** (A-RAG, APS-RAG, TREK,
EvoTrain-180K, CMT-RAG, BM25 …) and **24 matched nothing** (LLM, RAG, AI, QA,
GPU, POMDP, OSWorld, YOLOX-S, GPT-6 …). Gating on the vocabulary moves **19 of
150 questions** from `entity_anchored` to `semantic`, 66 → 47 overall.

A hardcoded stoplist of generic acronyms was the alternative. It fixes the
LLM/RAG/AI cases and leaves roughly half the 19 — the specific-but-unindexed
acronyms — still promising a channel that has nothing to give. It also rots:
every corpus change moves which acronyms are generic, and a list in source
cannot know that.

## Trade-offs accepted

- **A route now depends on corpus state.** The same question routes differently
  before and after an ingest. That is the intended semantics — the route is a
  claim about what retrieval can do here, not about the question in the
  abstract — but it means a route is no longer reproducible from the question
  text alone, and any future eval comparing routes must record the corpus.
- **Genuinely entity-anchored questions about unindexed artefacts now route
  `semantic`.** g117 asks about YOLOX-S, which the index does not hold; the
  dataset types it `entity_anchored` and the router no longer agrees. This is
  correct for retrieval and confusing for anyone reading the two side by side.
- **The vocabulary is loaded once per process.** A long-running server would
  serve a stale set after an ingest. Not a problem for eval drivers; it is a
  problem waiting for Phase 6.
- **Multi-word surface forms are deliberately not matched.** `large language
  models` links 42 of 54 papers, so matching it would re-introduce exactly the
  generic anchor this removes. Only single tokens that already look like
  artefacts are checked.
- **No measured retrieval change.** `search.py` runs every channel regardless
  of route, so this moves no recall number today. It is a correctness fix ahead
  of routing becoming load-bearing, not an improvement.
