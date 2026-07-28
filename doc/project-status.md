# Project Status

> Living document. Update at the end of every working session:
> current phase, what moved, what's blocked, what's next.

**Current phase:** 1 — Evaluation Harness (not started)
**Last updated:** 2026-07-28

## Roadmap

Phases are sequential. Each has numeric exit criteria — a phase is done when
the numbers exist, not when the code exists. Each phase gets a lab notebook
under `notebooks/phaseN_*/` whose conclusions graduate into ADRs and CI tests.

### Phase 1 — Evaluation Harness ← CURRENT

Build measurement before any retrieval code.

- [ ] Golden dataset: 50–100 questions across all six question types in
      [spec.md](spec.md), with labeled relevant papers/chunks
- [ ] Judge rubric (version-controlled): paraphrase tolerance, partial credit,
      abstention-is-correct rules
- [ ] Judge calibration: judge-vs-human agreement spot-check
- [ ] Ablation runner: every question runs with-retrieval and without-retrieval
- [ ] Per-stage metric hooks: retrieval recall@k, rerank NDCG, faithfulness

**Exit criteria:** harness runs in CI; ablation report shows per-question
answer delta; no-retrieval baseline accuracy is a known number.

### Phase 2 — Enriched Ingestion

Write-path intelligence: each paper produces four artifacts.

- [ ] Airflow DAG: fetch → Docling parse → enrich → index
- [ ] Section-aware chunks
- [ ] Claims: LLM extracts 5–15 atomic contributions per paper (once, at ingest)
- [ ] Entities: authors, method acronyms, datasets, arXiv IDs — linked to
      chunks/papers, link counts stored for damping
- [ ] Structured metadata in Postgres
- [ ] Hash-based claim dedup; batch-first with per-item fallback

**Exit criteria:** 500+ papers ingested; claim-extraction quality
spot-checked; cost-per-paper is a tracked number.

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

## Decisions made

- Generation: gpt-4o-mini; Judge: Claude Sonnet 4.6 on Bedrock — [ADR 0001](adr/0001-model-choices.md)

## Decisions pending

- Final project name (working name: DeepResearch)
- Embedding provider (default: Jina v3, carried from predecessor — revisit at
  Phase 3 with eval numbers)
- Reranker choice (candidates: Jina reranker API, local cross-encoder)
