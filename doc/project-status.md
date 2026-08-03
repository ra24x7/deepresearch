# Project Status

> Living document. Update at the end of every working session:
> current phase, what moved, what's blocked, what's next.

**Current phase:** 2 — Enriched Ingestion (Phase 1 substantially complete)
**Last updated:** 2026-07-29

## Roadmap

Phases are sequential. Each has numeric exit criteria — a phase is done when
the numbers exist, not when the code exists. Each phase gets a lab notebook
under `notebooks/phaseN_*/` whose conclusions graduate into ADRs and CI tests.

### Phase 1 — Evaluation Harness ✅ (2026-07-29, two items deferred)

Build measurement before any retrieval code.

- [x] Golden dataset: 33 questions across all six types from four 2026 RAG
      papers, human-verified (grow to 50–100 by Phase 3, rare types first —
      see sizing analysis in session log)
- [x] Judge rubric v2 (version-controlled), incl. mathematical equivalence
- [x] Judge calibration: 100% agreement over 29 pairs — uniform-abstention
      set only; re-calibrate on substantive answers in Phase 3
- [x] No-retrieval baseline: 0/29, zero parametric leakage
- [ ] DEFERRED → Phase 3: with-retrieval ablation delta (needs a pipeline
      to compare against)
- [ ] DEFERRED → when GitHub remote exists: harness in CI

**Exit criteria:** no-retrieval baseline is a known number ✅; judge
calibrated for observed verdict classes ✅; CI + ablation delta deferred as
noted above.

### Phase 2 — Enriched Ingestion

Write-path intelligence: each paper produces four artifacts.

- [~] Airflow DAG: fetch → Docling parse → enrich → index (stack up +
      healthcheck DAG green; full ingestion DAG lands in 2.6)
- [x] Section-aware chunks (100–800-word policy; captions deferred to
      section end; 4 golden papers → 150 chunks, 100% in band, deterministic)
- [x] Claims: LLM extracts 5–15 atomic contributions per paper (once, at ingest)
      — 45 claims over the golden papers, $0.0079/paper measured (Gate A)
- [x] Entities: authors, method acronyms, datasets, arXiv IDs — linked to
      chunks/papers, link counts stored for damping (177 entities, 500 links)
- [x] Structured metadata in Postgres (papers/chunks live; claims/entities/
      ingestion_runs tables migrated, filled by 2.4/2.6)
- [x] Hash-based claim dedup; batch-first with per-item fallback
- [x] Embedding + indexing: Cohere Embed v4 behind a swappable provider
      interface (ADR 0002); 1,518 chunks / 45 claims / 177 entities in
      OpenSearch, bibliographies excluded (ADR 0003)
- [x] Solvability audit v1: 31/31 evidence quotes pass Stage A (parsed text)
      and Stage B (single chunk); 6 fuzzy matches pending user review;
      Stage C (live index) re-runs in 2.6. Pattern from APS-RAG (2607.24663).
- [~] Frozen eval snapshot: `data/eval_snapshot.json` pins evalv1 (4 golden
      + 50 distractors, 2026-07-30); distractor ingest happens with 2.5

**Exit criteria:** 500+ papers ingested; claim-extraction quality
spot-checked; cost-per-paper is a tracked number; solvability audit passes
on the frozen eval snapshot.

### Phase 3 — Staged Retrieval Engine

The core of the project. Explicit stages, clean interfaces, each testable.

- [ ] Router: computable → SQL | semantic | entity-anchored | out-of-domain
- [ ] Fan-out: BM25 + dense (chunks), dense (claims), entity channel with
      IDF-style damping; over-fetch max(4×top_k, 60)
- [ ] Fusion with semantic gate (boosts reorder, never introduce)
- [ ] Cross-encoder rerank stage

**Exit criteria:** recall@10 and NDCG measured per-retriever and fused on the
golden set; each retriever proves added recall or is deleted (ADR either way).

### Phase 4 — Cost-Aware Agent Orchestration

- [ ] LangGraph: guardrail → route → retrieve → generate as the happy path
- [ ] Grade-and-rewrite as escape hatch, fired only on low rerank confidence
- [ ] Supervisor tools: search_papers, sql_metadata, get_claims, ingest_by_id
- [ ] Token/cost budget tracked per query (Langfuse)

**Exit criteria:** p50/p95 latency and cost-per-query measured; grading fires
on <30% of queries; accuracy within noise of the always-grade variant.

### Phase 5 — Attribution & Grounding

- [ ] Claim-level citations: each answer sentence → supporting chunk(s)
- [ ] Unsupported-residue detection (sentences with no supporting evidence)
- [ ] Calibrated abstention, verified by unanswerable golden questions
- [ ] Counterfactual perturbation tests in CI (wrong-paper chunk swaps →
      degrade or abstain, never bluff)

**Exit criteria:** statement-level attribution precision measured;
perturbation suite green in CI.

### Phase 6 — Production Hardening

- [ ] SLOs defined (e.g. p95 < 3s, cost < $0.01/query); Locust runs
      pass/fail against them
- [ ] Exact-match + semantic caching with hit-rate dashboards
- [ ] Index lifecycle: blue/green reindex with eval-gated cutover
- [ ] Eval-as-canary in the deploy pipeline
- [ ] EKS deployment (pattern known from predecessor project)

**Exit criteria:** a chunking change ships end-to-end through an eval-gated
reindex with no downtime.

### Phase 7 — Frontier (pick ONE, finish it)

Options — choose based on what Phase 3 eval results show is missing:

- Citation-graph traversal ("what built on X?") — only if relational golden
  questions demonstrably fail
- ColPali-style visual retrieval for table/figure questions
- Speculative prefetch for conversational follow-ups

**Exit criteria:** the chosen feature is measured against the golden set,
not just demoed.

## Session log

| Date | What happened |
|---|---|
| 2026-07-28 | Repo created; spec.md and project-status.md written; roadmap agreed |
| 2026-07-28 | architecture.md written; Phase 1 scaffolded: calibration notebook, golden dataset seed (6 examples), judge rubric v1 |
| 2026-07-28 | Bootstrap: uv + pyproject, connection test. Bedrock verified (judge: global.anthropic.claude-sonnet-4-6, see ADR 0001). OpenAI key pending. |
| 2026-07-29 | Phase 1 closed: 33-question dataset verified, baseline 0/29 (zero leakage), judge-human agreement 100%/29 pairs at rubric v2. CI + ablation delta deferred. |
| 2026-08-03 | Phase 2.4–2.5: enrichment live (Gate A, $0.0079/paper), evalv1 grown to 54 papers / 1,624 chunks, embedded with Cohere Embed v4 (~$0.08) into OpenSearch — 1,518 chunks indexed after excluding bibliographies (ADR 0003). Real-vector semantic search returns correct sections. Bugs found only at scale: container OOM at 50 papers, duplicate section-title id collision, NUL bytes in one PDF. Bedrock quota discovered to be token-bound (300k/min), so embed calls now retry on throttling. |
| 2026-07-30 | Phase 2.1–2.3: Docker stack (OpenSearch/Postgres/Airflow, lifted from predecessor + local Postgres) all healthy; fetch/parse/chunk modules TDD'd (68 tests); 4 golden papers → 150 chunks in Postgres; solvability audit v1 31/31 both stages after fixing math-tokenization matching and caption interleaving; evalv1 snapshot pinned (4+50 papers). Embeddings decided: Cohere Embed v4 on Bedrock (`global.cohere.embed-v4:0`, 1024-dim). 6 fuzzy audit matches await user review. |

## Decisions made

- Generation: gpt-4o-mini; Judge: Claude Sonnet 4.6 on Bedrock — [ADR 0001](adr/0001-model-choices.md)
- Embeddings: Cohere Embed v4 on Bedrock, behind a swappable provider interface; provider re-decided in Phase 3 on measured recall — [ADR 0002](adr/0002-embedding-provider.md)
- Bibliographies excluded from the search index, captured as citation entities instead — [ADR 0003](adr/0003-exclude-bibliography-from-index.md)

## Decisions pending

- Final project name (working name: DeepResearch)
- Embedding provider (default: Jina v3, carried from predecessor — revisit at
  Phase 3 with eval numbers)
- Reranker choice (candidates: Jina reranker API, local cross-encoder)
