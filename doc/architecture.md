# Architecture — DeepResearch (working name)

> Companion to [spec.md](spec.md) (what the product does) — this document says
> how. Non-obvious decisions get an ADR in `doc/adr/`; this file describes the
> current intended design, ADRs record why and what was rejected.

## Design thesis

Two ideas drive everything below:

1. **Write-path intelligence, read-path speed.** Papers are ingested once and
   queried forever, so expensive enrichment (claim extraction, entity linking)
   runs at ingestion. The query path is staged, cheap, and measurable; LLM
   reasoning at query time is an escape hatch, not a default.
2. **Explicit stages with clean interfaces.** Retrieval is not one opaque
   block. Every stage below can fail, be measured, and be improved
   independently — the eval harness (Phase 1) hooks into each boundary.

## System overview

```
WRITE PATH (Airflow, daily + on-demand)
  arXiv API → Docling parse → enrichment ─┬→ chunks index      (OpenSearch)
                                          ├→ claims index      (OpenSearch)
                                          ├→ entities index    (OpenSearch)
                                          └→ metadata          (Postgres)

READ PATH (FastAPI, per query)
  query → guardrail → router ─┬→ computable  → SQL over Postgres ──────────┐
                              └→ semantic    → fan-out retrieval           │
                                               (BM25 + dense chunks,      │
                                                dense claims, entities)    │
                                             → fusion + semantic gate      │
                                             → cross-encoder rerank        │
                                             → [low confidence? →          │
                                                grade / rewrite loop]      │
                                             → generation + attribution ───┤
                                                                           ▼
                                                        answer + claim-level citations
```

## Data stores

One unified retrieval engine, one relational store. No backend sprawl.

| Store | Holds | Why here |
|---|---|---|
| OpenSearch `chunks` | Section-aware chunks + dense vectors | BM25 + kNN + filters in one engine |
| OpenSearch `claims` | Atomic claims per paper + dense vectors | Smaller, cleaner retrieval unit for precise questions |
| OpenSearch `entities` | Entity → linked paper/chunk IDs + link counts | Rescues proper-noun/acronym queries embeddings miss |
| Postgres | Paper metadata (authors, dates, categories), ingestion state | Computable questions answered by SQL, not retrieval |
| Redis | Response cache (exact-match first, semantic later) | Cache hits skip the entire read path |

New retrieval channels are new OpenSearch indices, not new systems.

## Write path (Phase 2)

Airflow DAG, daily schedule plus on-demand by arXiv ID. Per paper:

1. **Fetch** — arXiv API, rate-limited with retries.
2. **Parse** — Docling; keep section structure.
3. **Chunk** — section-aware: sections of ~100–800 words become one chunk,
   larger sections split with overlap.
4. **Extract claims** — LLM distills 5–15 atomic contributions per paper.
   Runs once, at ingest. Hash-dedup against existing claims.
5. **Extract entities** — authors, method acronyms, datasets, arXiv IDs.
   Upsert with linked IDs; store link counts (used for damping at query time).
6. **Embed + index** — batch-embed all artifacts, bulk-index.

Resilience pattern throughout: batch first, fall back to per-item, log and
continue. Cost per paper is tracked and reported by the DAG.

## Read path

### Stage 1 — Guardrail

Out-of-domain queries (not about research) are rejected before any retrieval
cost is paid. Cheap classifier call; measured against out-of-domain golden
questions.

### Stage 2 — Router

Classifies the query and dispatches:

- **computable** → SQL generation over Postgres metadata. The answer is
  computed, not extracted ("how many cs.CL papers last month?").
- **semantic / entity-anchored** → retrieval fan-out (Stage 3).
- **mixed** → both, merged at generation.

Routing decisions are logged; router accuracy is measured as a confusion
matrix against golden-set labels.

### Stage 3 — Retrieval fan-out

Parallel retrievers with *different failure modes* (breadth over depth):

| Channel | Good at | Fails at |
|---|---|---|
| BM25 over chunks | Exact terms, IDs, acronyms | Paraphrase, synonymy |
| Dense over chunks | Topical/paraphrase match | Proper nouns, rare tokens |
| Dense over claims | Precise "what did paper X contribute" | Long contextual passages |
| Entity channel | "Kuzu", "LoRA", author names | Everything else (it only boosts) |

Over-fetch: `max(4 × top_k, 60)` candidates per channel — the first-pass
ranking is never the final ranking. Metadata constraints (category, date,
author) compile into the retrieval queries as pre-filters, never applied
post-hoc.

A channel stays in the fan-out only while eval shows it adds recall the
others miss (spec: "each retriever earns its place").

### Stage 4 — Fusion with semantic gate

Score-based fusion (not pure rank-based RRF) with one invariant:

> **Candidates must clear a raw semantic-similarity floor before any boost
> applies.** BM25 and entity signals reorder results; they can never
> introduce a candidate with no semantic relationship to the query.

Entity boosts are damped by link count (IDF-style): a rare entity ("Kuzu")
delivers nearly full boost; a ubiquitous one ("transformer") is damped to
almost nothing. Scores are normalized so they stay comparable when a channel
is absent.

### Stage 5 — Rerank

Cross-encoder rerank over the fused pool down to final top_k. This is the
precision stage; the fan-out is the recall stage. Rerank confidence is
exposed downstream — it decides whether Stage 6 fires.

### Stage 6 — Agentic escape hatch (conditional)

Only when rerank confidence is low:

- **Grade** — LLM scores retained candidates for relevance.
- **Rewrite** — if grading fails, reformulate the query and re-enter Stage 3
  (bounded retries).

This inverts the predecessor project's design, which graded every chunk on
every query. Target: fires on <30% of queries with accuracy within noise of
always-grading.

### Stage 7 — Generation + attribution

- Answer generated from surviving evidence with claim-level citations: each
  answer sentence maps to its supporting chunk/claim.
- Unsupported-residue detection flags sentences no evidence supports.
- **Abstention**: if the gate/rerank leaves insufficient evidence, the system
  says the corpus doesn't contain the answer and names the nearest related
  work — it never falls back to parametric memory with invented citations.

## Cross-cutting

### Evaluation hooks (Phase 1, used by every phase)

Each stage boundary emits measurable artifacts:

| Boundary | Metric |
|---|---|
| Router output | Routing accuracy (confusion matrix) |
| Fan-out output | Recall@k per channel and fused |
| Rerank output | NDCG, confidence calibration |
| Final answer | Judge accuracy, ablation delta, attribution precision, abstention calibration |

The golden dataset + version-controlled judge rubric live in the repo; the
harness runs in CI. Counterfactual tests (context ablation, wrong-paper
perturbation) are CI gates from Phase 5 on.

### Observability & cost

Langfuse trace per request spanning every stage; token/cost budget recorded
per query. Latency and cost are SLO'd in Phase 6 (targets set from measured
baselines, not guesses).

### Caching

Redis, cache-first: exact-match on normalized query (hash key + TTL) before
any stage runs. Semantic caching considered later only with hit-rate data.

### Index lifecycle (Phase 6)

Embedding-model or chunking changes ship via blue/green reindex: build the
new index alongside the old, run the golden set against it, cut over only if
eval passes. No in-place mutation of live indices.

## Code organization (planned)

```
src/
├── ingestion/        # arXiv client, parser, chunker, claim/entity extraction
├── retrieval/        # router, channels, fusion, gate, rerank — one module per stage
├── agent/            # LangGraph graph, nodes, tools (search, sql, ingest_by_id)
├── generation/       # prompts, attribution, abstention
├── evals/            # harness, judge, ablation/perturbation runners
├── api/              # FastAPI routers
└── config.py         # pydantic-settings
notebooks/phaseN_*/   # lab notebooks — evidence behind decisions (see ADRs)
doc/adr/              # decision records, each citing its notebook
```

Rules: notebooks import from `src/`, never the reverse. A notebook conclusion
graduates into an ADR and, where measurable, a CI eval test at the moment
it's drawn.

## What this deliberately is not

- Not multiple databases stitched together — OpenSearch is the single
  retrieval engine.
- Not streaming ingestion — daily batch + on-demand matches arXiv's cadence.
- Not agentic-by-default — the LLM loop is conditional, budgeted, and
  measured against the non-agentic path.
- Not graph-first — a citation-graph layer is a Phase 7 candidate only if
  relational golden questions demonstrably fail without it.
