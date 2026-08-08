# Project Status

> Living document. Update at the end of every working session:
> current phase, what moved, what's blocked, what's next.

**Current phase:** 3 — Staged Retrieval Engine (read path built and measured;
exit blocked on the golden set, deliberately)
**Last updated:** 2026-08-07

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

- [x] Airflow DAG: fetch → parse/chunk → enrich → embed/index → entities →
      report, one dynamically-mapped task per paper (docling accumulates
      memory across papers; a failed embed must not re-pay for enrichment).
      Manual-trigger only — `schedule=None`, since every run costs money.
- [x] Section-aware chunks (100–800-word policy; captions deferred to
      section end; 4 golden papers → 150 chunks, 100% in band, deterministic)
- [x] Claims: LLM extracts 5–15 atomic contributions per paper (once, at ingest)
      — 45 claims over the golden papers, $0.0079/paper measured (Gate A)
- [x] Entities: authors, method acronyms, datasets, arXiv IDs — linked to
      chunks/papers, link counts stored for damping (234 entities, 1,057
      links). Linking is corpus-wide and rebuildable without an LLM
      (`relink_entities`), which matters: re-chunking deletes links, so a
      free re-parse would otherwise cost a paid channel its data.
- [x] Structured metadata in Postgres (papers/chunks live; claims/entities/
      ingestion_runs tables migrated, filled by 2.4/2.6)
- [x] Hash-based claim dedup; batch-first with per-item fallback
- [x] Embedding + indexing: Cohere Embed v4 behind a swappable provider
      interface (ADR 0002); 1,518 chunks / 45 claims / 177 entities in
      OpenSearch, bibliographies excluded (ADR 0003)
- [x] Solvability audit v1: 31/31 evidence quotes pass Stage A (parsed text)
      and Stage B (single chunk); 6 fuzzy matches pending user review;
      Stage C (live index) re-runs in 2.6. Pattern from APS-RAG (2607.24663).
- [x] Frozen eval snapshot: `data/eval_snapshot.json` pins evalv1 (4 golden
      + 50 distractors, 2026-07-30), all 54 ingested — 1,624 chunks, 1,518
      indexed after excluding bibliographies, every chunk carrying a page
      range read from docling provenance rather than inferred.

**Exit criteria:** ~~500+ papers ingested~~ (amended 2026-08-04, see below);
claim-extraction quality spot-checked; cost-per-paper is a tracked number ✅
($0.0079/paper measured); solvability audit passes on the frozen eval
snapshot ✅ (31/31).

**Amendment — the 500-paper backfill moves after Phase 3.** The number was
set before any of this existed. Two facts now argue against spending it
early: the eval snapshot is *frozen* at 54 papers, so growing the
production corpus does not make Phase 3's measurement harder or more
meaningful; and if Phase 3 changes chunking or enrichment, 500 papers must
be re-parsed and re-enriched — paying ~$5 twice. The operational value of
scale-testing was already banked at 50 papers (OOM, duplicate-slug
collision, NUL bytes). Remaining justification for 500 is product
usefulness and pipeline durability, not evaluation quality; the
SLO-realism argument is dropped (~14k chunks is not where index
performance gets interesting).

### Phase 3 — Staged Retrieval Engine

The core of the project. Explicit stages, clean interfaces, each testable.

**Prerequisite — grow the golden set to ~150 questions before measuring.**
The error bar on recall is governed by the number of *questions*, not the
size of the corpus, so 29 answerable questions is a smoke test, not an
instrument. Sakai's power tables put ~110–180 topics as the requirement to
detect the ~10-point differences a reranker or chunking change actually
produces — which is exactly the size of effect this phase's exit criterion
asks us to act on. Two defects found in the existing set while checking
this (2026-08-04):

- **Lexical give-aways.** Mean question↔evidence word overlap is 0.30, but
  g015 (0.80), g026 (0.64) and g004 (0.60) hand BM25 the answer, biasing
  any hybrid-vs-dense comparison. Paraphrase before measuring — needs user
  sign-off, they are verified entries.
- **Multi-chunk evidence.** g013, g016 and g017 have their quote in two
  chunks each, both parts of one section: our own 100-word chunk overlap.
  Scoring must therefore treat relevance as *any chunk containing the
  evidence quote*, not a single pinned chunk id — otherwise recall is
  deflated for returning correct content. This also survives chunking
  changes, which a pinned id list would not.

- [~] Golden set grown to ~150 questions, stratified. **At 39 (2026-08-07),
      all eight types now represented.** Drafted one at a time and approved
      individually by the user. Two biases were being reproduced until
      measured: evidence stopped at page 9 in papers running to 45 pages
      (now reaches p35), and only 4 papers carried questions (now 9).
      Computable answers are corpus-dependent and rot silently — g020 sat
      stale at "4 papers" while the corpus grew to 54; nothing detects this
      yet. **Author: the user.** 30
      LLM-drafted questions were written and then deleted on 2026-08-04 —
      questions drafted by a model from quotable spans systematically select
      for extractable facts, which is the construct-validity risk, and
      human-authored questions remove it at the source rather than
      mitigating it. Budget 3–5 questions per paper (never more: 18 from one
      paper are not 18 independent samples) across ~28 papers, drawn from
      the ~48 corpus papers that carry no questions yet.
- [x] Router: rule-based, no LLM — an LLM router costs money per query and
      cannot be justified before evals show rules failing. `computable` still
      falls through to semantic retrieval; the SQL path is not built.
- [x] Fan-out: BM25 + dense (chunks), dense (claims), entity channel with
      IDF-style damping; over-fetch max(4×top_k, 60)
- [x] Fusion with semantic gate (boosts reorder, never introduce)
- [x] Cross-encoder rerank: Cohere `cohere.rerank-v3-5:0` on Bedrock, behind
      a `Reranker` protocol with a free identity implementation. Runs in
      `eu-central-1` — rerank is not offered in `ap-south-1`.
- [x] Retrieval eval: recall@k, NDCG@k, and reachability per channel and
      fused (`scripts/eval_retrieval.py`)

**Exit criteria:** recall@10 and NDCG measured per-retriever and fused on the
golden set ✅; each retriever proves added recall or is deleted (ADR either
way) — **blocked on the golden set, deliberately**. The number is evidence for
a decision, not a certification — Voorhees & Buckley found >10% gaps that still
mis-ranked systems at 50 topics, so a hard recall figure for a Phase 6 SLO must
come from production traffic, not this set.

**Measured 2026-08-07** on 29 answerable questions, k=10, over-fetch 60
(`notebooks/phase3_retrieval/`):

| channel | recall@10 | NDCG@10 |
|---|---|---|
| bm25 | 0.908 | 0.766 |
| dense_chunks | 0.856 | 0.684 |
| entities | 0.391 | 0.176 |
| dense_claims | n/a — see below | |
| **fused + rerank** | **0.977** | **0.912** |

Reachability 1.000: every gold chunk was surfaced by some channel inside the
over-fetch, so the ceiling reranking cannot raise is not binding.

**No ADR deletes a channel yet.** At n=29 only large effects are readable. The
reranker's +0.15 NDCG qualifies; the entity channel's contribution (+0.035
recall at weight 0.1) does not. Deleting a retrieval channel waits for the
larger golden set — the numbers above are for diagnosis and tuning only.

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
| 2026-08-07 | Phase 3 read path built and measured. Router, four channels, RRF fusion with the semantic gate, Cohere rerank (eu-central-1 — not offered in ap-south-1), orchestrator, and a retrieval eval. Fused recall@10 0.977, NDCG 0.912, reachability 1.000. Every gain traced to a measured cause: entity channel term-matched whole queries (0.000 → 0.391 once it probed n-grams), its full weight then *cost* 0.035 recall so a sweep set it to 0.1 as a tiebreaker, and the reranker's one regression (g033) turned out to be us withholding section titles from it. Claims measured separately — 4/4 where a relevant claim exists, but only 6 of 54 papers are enriched. Page provenance captured and backfilled; entity links rebuilt after a re-parse silently wiped them. |
| 2026-08-03 | Phase 2.4–2.5: enrichment live (Gate A, $0.0079/paper), evalv1 grown to 54 papers / 1,624 chunks, embedded with Cohere Embed v4 (~$0.08) into OpenSearch — 1,518 chunks indexed after excluding bibliographies (ADR 0003). Real-vector semantic search returns correct sections. Bugs found only at scale: container OOM at 50 papers, duplicate section-title id collision, NUL bytes in one PDF. Bedrock quota discovered to be token-bound (300k/min), so embed calls now retry on throttling. |
| 2026-08-08 | Refactor, no behaviour change: the duplication the scripts had accumulated moved into shared modules — `src/clients.py` (Bedrock/OpenSearch/Postgres handles), `src/goldenset.py`, `src/db/queries.py`, `src/evals/report.py`, `retrieval/channels/hits.py`, and `run_channels`/`fusion_weights`/`candidate_pool_size` in the orchestrator. Two real drifts closed: the eval scripts had hardcoded `localhost:9200` while the DAG read `OPENSEARCH__HOST`, and each eval restated the fusion weights it was supposed to be measuring. 42 tests added for the extracted units. |
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
