# Project Status

> Living document. Update at the end of every working session:
> current phase, what moved, what's blocked, what's next.

**Current phase:** 3 — Staged Retrieval Engine (read path built and measured
at n=136; both open anomalies diagnosed — next is the channel keep/delete
ADRs, which are the last exit criterion)
**Last updated:** 2026-08-14

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

- [x] Golden set grown to 150 questions (2026-08-08), stratified across all
      eight types, covering **54 of 54 papers**. Audit 159/159 quotes exact
      at both stages. Two biases were being reproduced until measured:
      evidence stopped at page 9 in papers running to 45 pages (the set now
      reaches p35, median evidence page 7), and only 4 papers carried
      questions. Growth was skewed away from `factual_single` (35% → 22% of
      the set) toward the types the eval could say least about:
      `definitional` 9→30, `computable` 9→24, `entity_anchored` 9→18,
      `unanswerable` 5→8, `out_of_domain` 2→4.
      **Provenance is split and it matters.** g001–g092 were authored or
      approved question-by-question by the user; g093–g150 were drafted by
      the model in pairs on 2026-08-08. The 2026-08-04 deletion of 30
      LLM-drafted questions still stands as the reason to distrust
      model-drafted questions: drafting from quotable spans selects for
      extractable facts, which is the construct-validity risk. That risk
      applies to g093–g150 and is *not* retired by the solvability audit,
      which proves quotes verbatim but says nothing about whether a question
      is fair or unambiguous. **The user verified all 61 outstanding entries
      (g049, g091–g150) on 2026-08-08 and the flags were cleared; the whole
      set of 150 is now human-verified.** The provenance split is recorded
      above because it stays relevant to interpreting eval results, not
      because verification is outstanding.
      Computable answers are corpus-dependent and rot silently — g020 sat
      stale at "4 papers" while the corpus grew to 54; nothing detects this
      yet, and the set now holds 24 `computable` questions. Budget 3–5
      questions per paper (never more: 18 from one paper are not 18
      independent samples); three pre-existing papers exceed it —
      `2607.24663` (10), `2602.03442` (9), `2606.21649` (7).
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
way) — **the re-run happened 2026-08-08 (R3, n=136); the ADRs are now the
only outstanding exit criterion, and the entity channel's 0.260 recall is
the evidence they turn on**. The number is evidence for
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

**Superseded 2026-08-08 by the n=136 re-run — see `doc/eval-log.md` (R3).**
Fused recall@10 0.940, NDCG 0.817 with Cohere rerank; 0.907 / 0.681 without.
Every figure is lower than the table above and none of it is a regression:
no retriever code changed, the question set grew from 29 to 136 and got
harder by design. `multi_paper` recall of 0.569 across 12 questions is the
newly-visible weakness. The old numbers are kept for their diagnostic
history.

**The table above is stale as of 2026-08-08.** They were measured on 29
answerable questions; the golden set now holds ~138. Nothing about the
retriever changed — the measuring instrument did — so the table above and
`notebooks/phase3_retrieval/README.md` describe a different, smaller
experiment and must not be compared against the re-run. Re-running costs one
query embedding plus one Cohere rerank call per question, roughly $0.20–0.30
(live API — ask first). The 61 draft entries were verified on 2026-08-08,
so the re-run is now the only thing standing between here and the channel
keep/delete ADRs.

### Phase 4 — Cost-Aware Agent Orchestration

- [ ] LangGraph: guardrail → route → retrieve → generate as the happy path.
      **Fix the router before routing becomes load-bearing:** `_is_artefact_token`
      treats any acronym as an entity anchor, so every question mentioning LLM,
      RAG or BERT routes `entity_anchored` — g080 does, while the entity channel
      returns zero hits for it (`doc/eval-log.md` D1). Inert today only because
      `src/retrieval/search.py` runs all four channels regardless of route.
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
| 2026-08-14 | Both open R3 anomalies diagnosed (`doc/eval-log.md` D1, 4 embed calls ~$0.00002; no source file changed). **g080 — the defect is in the question, not the retriever.** Its gold chunks are indexed with vectors, but the question's only content words (`llm`, `papers`, `weakness`) occur **zero** times in either gold chunk: bm25 returns the right paper's wrong section at rank 0, entities returns nothing at all. It is a corpus-level meta-question whose referent no retriever receives, so it is also *not* evidence about query decomposition — expect it to stay at 0.0 there. It alone holds reachability at 0.993, and `multi_paper` would read 0.621 rather than 0.569 without it. **g084 — a knife-edge, not a lever.** The semantic gate is exonerated (both gold chunks pass it); gold lands at fused ranks 10 and 13 against a k=10 cutoff decided by **0.00007**, with 8 of the top-10 being one paper's boilerplate. Entity weight and the RRF constant each flip the outcome non-monotonically and the shipped values of both land on the wrong side, so no config exceeds 0.500 — tuning either would be fitting the dev set. Corrects an earlier reading: R4's cap does not rescue g084's gold, it swaps which gold survives. First empirical support for query decomposition, since every within-one-ranking lever tops out at 0.500. A free corpus-wide anchor scan (r=+0.42 vs fused recall) found `multi_paper` systematically anchor-poor (mean 2.87 vs 4.24–4.87) and two questions worse-anchored than g080 — g088 (`the`, 0.02) and g087 (`with`, 0.23). |
| 2026-08-10 | Rerank-then-diversify experiment: rejected (`doc/eval-log.md` R5, ~$0.15). Applying the per-paper cap of 3 at selection time — after Cohere scores all 60 candidates, R4's lesson applied — still lost 10 questions to gain a third of one: fused recall 0.940 → 0.875, `multi_paper` 0.569 → 0.597. The reranker itself ranks 3+ same-paper chunks above gold on the regressed questions, so within-paper order is unreliable under both RRF and cross-encoder scoring: per-paper caps are the wrong lever for `multi_paper` at any pipeline stage. Surviving direction, recorded not built: query decomposition (a two-paper question retrieves as two sub-queries). Code reverted; both experiments cost two eval runs and ~30 lines each, which is the eval-first loop working as intended. |
| 2026-08-09 | Per-paper cap experiment: rejected on a pre-registered paired comparison (`doc/eval-log.md` R4, free run). A cap of 3 fused hits per paper between fusion and rerank — built to attack `multi_paper` 0.569 — regressed 30 questions and improved 1: identity fused recall 0.907 → 0.719, every type down including `multi_paper`. Root cause: within-paper RRF rank is a poor relevance proxy, so the cap deletes gold chunks from the candidate pool before anything relevance-aware sees them; the lesson (diversify after relevance scoring, never filter before it) is in the R4 entry. Same entry corrects R3's g038 anomaly — no bug, empty evidence by design pending the SQL-over-metadata route — and formalizes golden-set dev-set discipline. Cap code revert pending user decision. |
| 2026-08-08 | Retrieval eval re-run at n=136 (`doc/eval-log.md` R2/R3, ~$0.15). Fused recall@10 0.940 / NDCG 0.817 with Cohere rerank, 0.907 / 0.681 without — the reranker's +0.136 NDCG is now decisive (better on 56 questions, worse on 14), where at n=29 it was only suggestive. Every headline number fell against the n=29 run and none of it is a regression: the retriever is unchanged, the exam got harder. Two things only the larger set could show — `multi_paper` recall 0.569 across 12 questions while every other type sits at 0.93–1.00, and the entity channel weakening to 0.260, which is the evidence the deferred keep/delete decision was waiting on. Two anomalies logged unexplained: g080 is unreachable by every channel, and g038 is silently excluded for having no matching chunk despite passing the solvability audit. |
| 2026-08-08 | Golden set 92 → 150, then verified end-to-end by the user — all 61 outstanding `draft_unverified` flags cleared, so the full set of 150 is human-verified and the Phase 3 exit criterion is unblocked. Growth details: Coverage closed to 54/54 papers (g091–g092), then 58 questions added in pairs. Growth deliberately skewed to the thin types — `definitional` and `computable` roughly tripled — since half the set was `factual_single`/`negation` and the eval could say least about abstention and multi-fact composition. Evidence pushed deeper: 60% of new page references beyond p9 vs 18% before, deepest p31. The mid-word quote check fired seven times, all on model-drafted quotes copied from a truncated print window (`framin`, `amon`, `config`, `Exponentia`, `leg`, `exp`, `f`) — the same failure that caused g051's factual error; one (g134) had also propagated a wrong word into its reference answer. All repaired to sentence boundaries and re-verified, audit 159/159. 61 entries remain `draft_unverified`. Also confirmed the 55th paper in Postgres (`2607.29600`) is tagged `corpus: sandbox` and correctly outside evalv1, and that the 106 Postgres chunks absent from the index are all `references` sections, excluded by design (ADR 0003) with zero stale docs. |
| 2026-08-07 | Phase 3 read path built and measured. Router, four channels, RRF fusion with the semantic gate, Cohere rerank (eu-central-1 — not offered in ap-south-1), orchestrator, and a retrieval eval. Fused recall@10 0.977, NDCG 0.912, reachability 1.000. Every gain traced to a measured cause: entity channel term-matched whole queries (0.000 → 0.391 once it probed n-grams), its full weight then *cost* 0.035 recall so a sweep set it to 0.1 as a tiebreaker, and the reranker's one regression (g033) turned out to be us withholding section titles from it. Claims measured separately — 4/4 where a relevant claim exists, but only 6 of 54 papers are enriched. Page provenance captured and backfilled; entity links rebuilt after a re-parse silently wiped them. |
| 2026-08-03 | Phase 2.4–2.5: enrichment live (Gate A, $0.0079/paper), evalv1 grown to 54 papers / 1,624 chunks, embedded with Cohere Embed v4 (~$0.08) into OpenSearch — 1,518 chunks indexed after excluding bibliographies (ADR 0003). Real-vector semantic search returns correct sections. Bugs found only at scale: container OOM at 50 papers, duplicate section-title id collision, NUL bytes in one PDF. Bedrock quota discovered to be token-bound (300k/min), so embed calls now retry on throttling. |
| 2026-07-30 | Phase 2.1–2.3: Docker stack (OpenSearch/Postgres/Airflow, lifted from predecessor + local Postgres) all healthy; fetch/parse/chunk modules TDD'd (68 tests); 4 golden papers → 150 chunks in Postgres; solvability audit v1 31/31 both stages after fixing math-tokenization matching and caption interleaving; evalv1 snapshot pinned (4+50 papers). Embeddings decided: Cohere Embed v4 on Bedrock (`global.cohere.embed-v4:0`, 1024-dim). 6 fuzzy audit matches await user review. |

## Decisions made

- Generation: gpt-4o-mini; Judge: Claude Sonnet 4.6 on Bedrock — [ADR 0001](adr/0001-model-choices.md)
- Embeddings: Cohere Embed v4 on Bedrock, behind a swappable provider interface; provider re-decided in Phase 3 on measured recall — [ADR 0002](adr/0002-embedding-provider.md)
- Bibliographies excluded from the search index, captured as citation entities instead — [ADR 0003](adr/0003-exclude-bibliography-from-index.md)

## Decisions pending

- **Disposition of g080, g087, g088** (`doc/eval-log.md` D1). Three
  `multi_paper` questions whose wording gives retrieval nothing to match:
  g080's content words appear zero times in its own gold chunks, and g087 and
  g088 share only `with` and `the` with theirs. Options per question: reword
  to carry retrievable content, retire with the reason recorded, or keep as a
  documented ceiling on `multi_paper` and reachability. **User's call** —
  golden-set authority. Until then `multi_paper` (0.569, n=12) is bounded by
  defects in three of its twelve questions, and any decomposition experiment
  should exclude g080 from its decision rule.
- **Held-out golden split.** The golden set is a dev set: it has tuned
  `entity_weight`, the gate config, and the rejected per-paper cap (R4), so
  its numbers measure fit to these 150 questions, not generalization. When
  the set next grows (~200), freeze a stratified ~50-question split that is
  never inspected during development and runs only at phase gates. Until
  then, golden numbers carry the dev-set caveat per `doc/eval-log.md` R4.
- Final project name (working name: DeepResearch)
- Embedding provider (default: Jina v3, carried from predecessor — revisit at
  Phase 3 with eval numbers)
- Reranker choice (candidates: Jina reranker API, local cross-encoder)
