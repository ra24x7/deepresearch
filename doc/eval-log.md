# Eval Log

> Append-only ledger of every eval run. One entry per run, newest first.
> Never edit a past entry's numbers — they are the record of what was true
> when the run happened. Corrections go in a new entry that cites the old one.
>
> **Every entry must state the dataset, the code state, and the config.** A
> number without those three is not comparable to anything. Per `CLAUDE.md`,
> results may not be compared across a rubric, generation-model, or dataset
> change without flagging the break — the `Comparable to` field below is
> where that flag lives.

## Index

| Date | Run | Dataset | Headline |
|---|---|---|---|
| 2026-08-17 | S1 answer-path sample, 8 questions, Cohere | golden 150 (8 sampled) | wiring proven; **$0.00183/query**; two defects found and fixed |
| 2026-08-15 | C1 cost correction (no re-run) | — | recorded rerank costs understated **≥1.8×**; embed costs unpriced |
| 2026-08-14 | R6 entity-weight sweep + claims ablation, identity | golden 150 (136 scored) | entity 0.1 confirmed optimal but worth only **+0.0111**; claims **±0.0000** |
| 2026-08-14 | D2 spike, `multi_paper` fix candidates (not a scored run) | golden 150 (9 questions probed) | **no achievable variant reaches the oracle — do not build decomposition yet**; most losses are `k=10` cutoff artefacts |
| 2026-08-14 | D1 diagnostic, g080 + g084 (not a scored run) | golden 150 (nothing scored) | both anomalies explained; **no dataset-level numbers** |
| 2026-08-10 | R5 retrieval, rerank-then-diversify cap 3, Cohere | golden 150 (136 scored) | fused recall@10 **0.875** — rejected |
| 2026-08-09 | R4 retrieval, per-paper cap 3, identity rerank | golden 150 (136 scored) | fused recall@10 **0.719** — cap rejected |
| 2026-08-08 | R3 retrieval, Cohere rerank | golden 150 (136 scored) | fused recall@10 **0.940**, NDCG **0.817** |
| 2026-08-08 | R2 retrieval, identity rerank | golden 150 (136 scored) | fused recall@10 0.907, NDCG 0.681 |
| 2026-08-07 | R1 retrieval, both rerankers | golden ~39 (29 scored) | fused recall@10 0.977, NDCG 0.912 |
| 2026-07-29 | Judge calibration + no-retrieval baseline | golden 33 (29 scored) | judge agreement 100%, baseline 0/29 |

---

## S1 — 2026-08-17 — Answer-path sample, 8 questions — wiring proven, two defects found

**Command:** `uv run python scripts/eval_answers.py --corpus evalv1 --ids g001,g007,g016,g018,g020,g021,g035,g036`
**Report:** `notebooks/phase4_orchestration/answer_eval.json`
**Cost:** $0.0146 per pass, run twice (before and after the fixes below) — $0.029
total. Live Bedrock, user-authorized.

**Purpose:** first end-to-end execution of the Phase 4 path. Not a measurement
of quality — eight questions cannot measure anything. It exists to prove the
wiring and to replace an estimated cost-per-query with a measured one.

### State at time of run

| | |
|---|---|
| Golden set | 150, human-verified; **8 sampled**, one per type |
| Corpus | `evalv1`, 1,518 chunks |
| Code | commit `e26aa61` (first pass), plus the two fixes below (second pass) |
| Config | k=10, over-fetch 60, Cohere rerank, Haiku generation, Sonnet 4.6 judge, rubric v2 |

### Comparable to

**Nothing.** This is a different instrument measuring a different thing —
answer pass rate, not retrieval recall — at n=8. It sets no baseline. The
first comparable figure will be the full 150-question run.

### Measured

| | |
|---|---|
| cost per query | **$0.00183** |
| implied full 150-question run | **~$0.27** |
| latency p50 / p95 | 3.3s / 6.4s |
| pass rate | 0.750 after fixes (6/8) — **not meaningful at n=8** |

The prior estimate for a full run was ~$2.70, an order of magnitude high. The
guardrail also demonstrated its purpose: the `out_of_domain` question completed
in 0.0s having made no retrieval and no generation call, so it cost nothing.

### Defect 1 — the judge does not use the ABSTAINED label on unanswerable questions

On g021 the system abstained perfectly and the judge returned **CORRECT** while
citing rule 4 by name in its reason ("the candidate correctly abstained rather
than bluffing"). The rubric defines ABSTAINED as "the system declined to
answer" and rule 4 makes ABSTAINED the pass on these types, so scoring on the
verdict marked a textbook abstention as a failure.

**This path was never calibrated.** Phase 1's 29 pairs were all *answerable*
questions against a uniformly abstaining baseline, so abstention on an
*unanswerable* question never occurred once — the caveat recorded in
`notebooks/phase1_eval_harness/README.md`, arriving as predicted.

**Fix:** abstention is now decided structurally, by exact match against the
sentinel the generator and guardrail both emit, and the judge's label is
ignored on those two types (`src/evals/answer_eval.py`). Chosen over adding
`expected_behavior` to the judge prompt, which would have bumped the rubric
version and invalidated every verdict recorded under v2.

### Defect 2 — the generator appended prose after refusing

On g018 the model emitted the abstention sentence and then continued for
another 1,200 characters describing what the passages *do* contain. Exact-match
detection failed, and a refusal followed by substantive content is bluffing
with a disclaimer attached.

**Fix:** the generation prompt now states that the sentence is the entire
reply, naming the specific failure (no explanation, no summary of what the
passages say, no partial answer). After the fix g018's answer is 47 characters
— the sentinel alone.

Both fixes verified by re-running the identical sample: pass rate 0.500 → 0.750,
with g018 and g021 moving to PASS.

### Two failures that remain, both known

- **g020 (`computable`)** — answered "1 paper" against a reference of 54. This
  is the unbuilt SQL-over-metadata route: the router classifies `computable`
  and then falls through to semantic retrieval, exactly as
  `doc/project-status.md` predicts. Not an answer-quality failure.
- **g036 (`definitional`)** — the answer states the core distinction correctly
  and omits the enumerated counter-examples; the judge applied **rule 3, no
  partial credit**. Answers were checked against the token cap and are not
  truncated (longest ~324 tokens against 1024), so this is a genuine rule-3
  outcome — the **first live instance of the revisit condition the rubric
  itself records** for rule 3. Whether it is unfair is the user's call.

---

## C1 — 2026-08-15 — Cost correction: recorded rerank spend understated

**No run.** No question was retrieved, scored or judged. This entry corrects
**cost figures only** — every recall, NDCG and verdict in this log stands
unchanged.

**Trigger:** building the per-model rate table for `src/llm/cost.py` (Phase 4)
required looking up Cohere's published Bedrock rates for the first time.

### What the published rate actually is

AWS Bedrock, Cohere section: **Rerank 3.5 is $2.00 per 1,000 queries**, where

> a query can contain up to 100 document chunks. If the query contains more
> than 100 document chunks, it is counted as multiple queries… each document
> can only contain up to 500 tokens (inclusive of the query and document's
> total tokens), and if the token length is higher than 512 tokens, it is
> broken down into multiple documents.

### The correction

| run | rerank calls | recorded cost | rerank alone, at list |
|---|---|---|---|
| R3 (2026-08-08) | 136 @ 60 docs | ~$0.15 | **≥ $0.272** |
| R5 (2026-08-10) | 136 @ 60 docs | ~$0.15 | **≥ $0.272** |

Each run's recorded figure is **at least 1.8× too low**, and the recorded
figure was supposed to cover query embeddings *as well as* rerank.

**"At least" is doing real work in that sentence.** 60 documents is under the
100-document cap, so each call bills as one query *only if every document fits
in 512 tokens*. Chunks in this corpus run 100–800 words, so the longer ones
split into multiple documents; a call can therefore cross 100 documents and
bill as two queries. The true figure is somewhere between $0.272 and roughly
double that, and cannot be pinned down without per-document token counts.

### Two further corrections to embed accounting

**Embed v4 has no published price.** Cohere Embed **v4** — the model this
project uses (`global.cohere.embed-v4:0`) — does not appear on the public
Bedrock pricing page at all; only Embed **3**, and only as provisioned-throughput
hourly rates. So **every embedding cost in this log is unverified**, not merely
imprecise. `CostLedger` now counts embed calls and reports them through an
`unpriced` field rather than costing them at zero.

**Embed call counts are themselves understated ~2×.** Until ADR 0005,
`search_dense_chunks` and `search_dense_claims` each called `embed_query`
independently, so one question cost **two** embed calls, not one. R3 and R5
predate that change: each made ~272 embed calls, not the 136 implied by their
entries. R6 and D2 used a caching wrapper and are unaffected.

### Root cause: the harness never measured cost

The figures in R1–R5 were **estimates written by hand at the time**, not
measurements — `scripts/eval_retrieval.py` computes no cost and records none.
There was nothing to catch the error, which is why it survived five entries and
surfaced only when an unrelated task required the published rate.

This is the same failure shape as the `ingestion_runs` gap found the same week:
the schema for recording cost exists and works, but the run that mattered never
wrote to it.

### What this changes

- **No result changes.** Recall, NDCG, reachability, verdicts and every
  keep/delete decision are untouched. Cost never entered a decision rule.
- **Treat every dollar figure in R1–R5 as a lower bound of unknown tightness**,
  not as a measurement. The same applies to `$0.0079/paper` and the `$0.389`
  full-corpus enrichment figure, which were computed from token counts at
  **Anthropic first-party rates** — also unverified against Bedrock.
- **Phase 4 must record cost, not estimate it.** The exit criterion is
  cost-per-query measured; that means persisted per run from token counts and
  call counts, with `unpriced` surfaced alongside, so a gap like this announces
  itself instead of waiting for someone to read a pricing page.
- **Still open:** the AWS bill reconciliation (~$0.80 claimed, 2026-07-28 to
  2026-08-14) that would settle whether first-party Claude rates apply on
  Bedrock at all.

---

## R6 — 2026-08-14 — Entity-weight sweep and claims ablation at n=136, identity reranker

**Command:** one retrieval pass over the scored set in the session scratchpad,
reusing the shipped channels, `fuse()` and `score_question`; every variant
recomputed from the same cached channel results, so the API cost is one query
embedding per question.
**Report:** no JSON written — the numbers are in this entry.
**Cost:** 136 live Cohere embed calls, ~$0.001, user-authorized. Identity
reranker, **no rerank calls**.

**Purpose:** supply the two numbers ADR 0004 and ADR 0005 each identified as
missing. Run before closing Phase 3, whose exit criterion requires an ADR for
every retriever either way.

### State at time of run

| | |
|---|---|
| Golden set | 150 questions, human-verified — identical to R2–R5 |
| Scored | 136 — same exclusions as R2/R3 (8 `unanswerable`, 4 `out_of_domain`, g038) |
| Corpus | `evalv1`, 1,518 chunks / 638 claims / 1,624 entities |
| Code | commit `e15d1b5`, **unmodified** |
| Config | k=10, over-fetch 60, gate `(dense_chunks, dense_claims)`, **identity** reranker; `entity_weight` and `dense_claims` membership are the swept variables |

### Comparable to

**R2 — directly, and used as the trust check.** At the shipped
`entity_weight = 0.1` with claims in fusion, R6 reproduces R2 exactly: recall
**0.9069**, NDCG **0.6814**. Not comparable to R3/R5, which used Cohere rerank.

### Results — entity weight sweep (claims in fusion, as shipped)

| entity weight | recall@10 | NDCG@10 |
|---|---|---|
| 0.0 (off) | 0.8958 | **0.6855** |
| 0.05 | 0.9032 | 0.6844 |
| **0.1 (shipped)** | **0.9069** | 0.6814 |
| 0.25 | 0.8971 | 0.6756 |
| 0.5 | 0.8750 | 0.6689 |
| 1.0 | 0.8750 | 0.6607 |

Per type, weight 0.0 → 0.1: `factual_single` 0.970 → 1.000, `negation`
0.929 → 0.976, **`multi_paper` 0.556 → 0.514**; `computable` (0.871),
`definitional` (0.917) and `entity_anchored` (0.944) unchanged at both.

### Results — claims ablation (`entity_weight` held at 0.1)

| | |
|---|---|
| claim docs in fused top-10 | 15 slots of 1,360 (**1.10%**) |
| questions with ≥1 claim in top-10 | 8 of 136 |
| chunk recall / NDCG **with** `dense_claims` | 0.9069 / 0.6814 |
| chunk recall / NDCG **without** `dense_claims` | **0.9069 / 0.6814** |
| delta | **+0.0000 / +0.0000**, every type unchanged |

The entity sweep is identical with claims removed from fusion, so the two
variables do not interact.

### Findings

**1. `entity_weight = 0.1` is confirmed as the recall optimum at n=136 — and
is worth a third of what n=29 claimed.** The superseded sweep credited it with
+0.0345 recall; the current instrument says **+0.0111**. NDCG falls
monotonically with the weight, so the channel always costs ranking quality and
is repaid only in recall, in a narrow band around 0.1.

**2. The channel's gain is paid for by the weakest type.** It buys
`factual_single` (+0.030) and `negation` (+0.047) and costs `multi_paper`
(−0.042). It does **not** move `entity_anchored`, the type named after it,
which weakens the intuition that it has a distinct competence.

**3. `dense_claims` is inert for chunk retrieval — provably.** Removing it from
fusion changes recall and NDCG by exactly zero across all 136 questions and
every type. It occupies 1.10% of top-10 slots, and those slots displace only
non-gold chunks. This kills both the argument that it steals slots and any
retrieval-side argument for keeping it.

### What this settles

Both ADR gaps are closed. **ADR 0004** is no longer justified by a superseded
number: it is a real but marginal trade (+0.0111 recall vs −0.0041 NDCG and
−0.042 on the weakest type). **ADR 0005** becomes a product decision rather
than a retrieval one, since retrieval is measurably indifferent to the claims
channel.

Standing caveat: R4's dev-set discipline applies. These 150 questions have now
been used to tune `entity_weight` twice; the held-out split in
`doc/project-status.md` remains pending.

---

## D2 — 2026-08-14 — Spike: what would actually fix `multi_paper`? — BUILD NOTHING YET

**Commands:** throwaway probes in the session scratchpad against the live
`evalv1` index, reusing `score_question` / `relevant_chunk_ids` from
`src/evals/retrieval_eval.py` and the shipped channels and `fuse()` so numbers
are comparable to the stored reports by construction. No harness run, no report
file written, **no source file changed**.
**Cost:** ~70 live Cohere embed calls (query embeddings, cached per unique
string), well under $0.01, user-authorized. Identity reranker throughout — **no
rerank calls**. Note: the plan estimated 40–60 calls; the extra probe (d) took
it to ~70.

### State at time of run

| | |
|---|---|
| Golden set | 150 questions, human-verified — identical to R2–R5 |
| Scored | **none dataset-wide**; 9 `multi_paper` questions probed individually |
| Corpus | `evalv1`, verified live: 1,518 chunks / 638 claims / 1,624 entities |
| Code | commit `bffbc6f`, **unmodified** |
| Config | k=10, over-fetch 60, entity weight 0.1, gate `(dense_chunks, dense_claims)`, **identity** reranker |

### Comparable to

**Nothing dataset-wide, and it supersedes nothing.** Per-question baselines are
the identity-reranker numbers from **R2** (not R3 — R3 used Cohere). Probe 0
below is the trust check that makes the rest comparable at all.

### Scope and why

D1 classified the twelve `multi_paper` questions: 4 already fine, 3 lost
downstream (g034, g017, g084), 5 coverage gaps — of which g080, g087 and g088
are **question defects**, not retrieval failures. Excluding those three leaves
**five genuine failures**, split 3 downstream / 2 coverage. Targets: g034,
g017, g084, g148, g108. Controls: g016, g071, g077, g138.

### Probe 0 — trust check: PASS

The spike harness reproduced all 27 stored per-question numbers exactly
(fused vs R2, bm25 and dense_chunks vs R3). **Correction to the plan's control
criterion:** under the identity reranker the controls are not all 1.000 —
g016 is 0.667 and only reaches 1.000 with Cohere. Controls were therefore
judged against their identity baselines.

### Probe 1 — loss forensics

| question | where the gold went |
|---|---|
| g034 | 2 of 3 gold in top-10; third **out at fused rank 15, margin 0.00263**. Top-10 is 7 chunks from one paper, 3 from the other. BM25 alone had all three at k=10. |
| g017 | 1 of 3 in top-10; the two `2607.24663` chunks out at ranks 29 and 13. That paper holds **5 of the 10 slots — none of them its gold**. |
| g084 | both out, at ranks 10 and 13; margins **0.00007** and 0.00154. Top-10 is 8/10 one paper. |
| g148 | 1 of 2 in; the other out at **rank 58, margin 0.01451**, found only by dense_chunks (bm25 never returned it). |
| g108 | **fused top-10 is 10/10 a single paper** — the second paper gets zero slots. One of its gold chunks is returned by **no channel at all** inside the over-fetch; another sits at rank 11 with margin 0.00076. |

Two more knife-edges beyond D1's g084: g108 at 0.00076 and g034 at 0.00263.
Paper monopoly of the top-10 is the recurring shape, not a one-off.

### Probe 2 — four candidate fixes, scored identically

Mean recall@10 over the five targets; controls listed separately.

| variant | g034 | g017 | g084 | g148 | g108 | **mean** |
|---|---|---|---|---|---|---|
| baseline (shipped) | 0.667 | 0.333 | 0.000 | 0.500 | 0.000 | **0.300** |
| **(a) question-only split** | 0.667 | 0.333 | 0.000 | 0.500 | 0.000 | **0.300** |
| **(b) ORACLE split** *(ceiling)* | 1.000 | 0.667 | 1.000 | 1.000 | 0.333 | **0.800** |
| **(c) per-paper round 2** *(no LLM)* | 0.667 | 0.333 | 0.500 | 0.500 | 0.333 | 0.467 |
| **(d) title-augmented** *(no LLM)* | 1.000 | 0.333 | 1.000 | 0.500 | 0.000 | 0.567 |

Controls (identity baseline → variant):

| | g016 | g071 | g077 | g138 |
|---|---|---|---|---|
| baseline | 0.667 | 1.000 | 1.000 | 1.000 |
| (c) per-paper round 2 | 0.667 | **0.500** | **0.500** | 1.000 |
| (d) title-augmented | **0.000** | **0.500** | **0.000** | 1.000 |

### Findings

**1. Question-only decomposition is worth nothing — 0 of 5, not a single
question moved.** This includes the two questions that name both subjects in
the question text (g017 "A-RAG and APS-RAG", g108 "accounting and office-work"),
where a clean per-paper split is trivially derivable. **This kills the
rule-based decomposer**, which was the free option.

**2. The oracle ceiling is real and high** — 0.300 → 0.800, with g084 going
0.000 → 1.000. The gold chunks *are* retrievable. What is missing is knowing
what to ask.

**3. But the ceiling is partly circular, so it overstates.** The oracle
sub-queries encode where the answer lives ("five-dimensional rubric score
range", "cost ablation budget cap") — the very thing retrieval is supposed to
find. The genuinely achievable half of the oracle is *paper identity*, which is
available for free from paper titles. That is exactly what (d) tested.

**4. Both no-LLM approximations are net negative.** (c) helps two targets and
halves two controls. (d) helps two targets and takes **two controls to 0.000**.

**5. (d)'s wins are an artifact, and the correlation is perfect.** Gold chunk
location explains every result: g084 (2/2 gold are abstract chunks) 0.000 →
1.000 and g034 (1/3 abstract) 0.667 → 1.000, while **every question with zero
abstract gold either stayed flat or regressed** — g016, g071 and g077 all have
0/N abstract gold and all fell. Putting a paper's title in the query biases
retrieval toward that paper's abstract. It is not finding answers better; it is
finding abstracts.

### The cheapest lever is not a fix at all — it is `k`

Derived from Probe 1's recorded fused ranks; **no new retrieval and no new API
calls**. Most lost gold is not lost, only past the cutoff:

| question | gold ranks (0-indexed) | recall@10 | recall@20 |
|---|---|---|---|
| g034 | in top-10, in top-10, **15** | 0.667 | **1.000** |
| g017 | in top-10, **13**, 29 | 0.333 | **0.667** |
| g084 | **10**, **13** | 0.000 | **1.000** |
| g148 | in top-10, 58 | 0.500 | 0.500 |
| g108 | **11**, **18**, absent | 0.000 | **0.667** |
| | | **0.300** | **0.767** |

**0.767 beats every variant built and tested above, with zero new code**, and
sits just under the unshippable oracle's 0.800.

**This is not evidence that retrieval improved.** Comparing recall@20 against
recall@10 is not a fair comparison — a larger k always helps, and the figure
above is reported only against these five questions, not the set. What it *is*
evidence for is that **k=10 may be the wrong product parameter**. The binding
constraint is not 10; it is how many chunks the Phase 4 generation step can
afford in context. If that budget is 20, most of these failures cease to be
failures without any retrieval change at all.

**Do not read this as a tuning result and do not change k on it.** The proper
test is end-to-end answer quality at k=10 vs k=20 against cost and latency,
which needs the generation step that does not exist yet. Recorded here so the
option is not lost.

### Verdict

**Build nothing yet.** No achievable variant reproduces the oracle's gains, and
the two mechanical approximations both trade control questions for target
questions — the same failure shape that sank R4 and R5.

The only untested route to the oracle is an LLM decomposer. This spike does not
clear it: the achievable information an LLM could add (which papers) is what (d)
supplied and (d) failed; the information that actually drives the ceiling (which
*section* holds the answer) is what retrieval exists to discover. That is the
circularity, and it should be stated in any future proposal rather than assumed
away.

Independently: **n=5 cannot support an architectural decision.** Nine of the
twelve `multi_paper` questions are usable at best, three of those are defective,
and R4's dev-set discipline applies to every number here. Growing the
`multi_paper` count should precede any build.

### What this changes

- **Decomposition is no longer "the surviving direction" by default.** R5
  recorded it as plausible-but-unmeasured and D1 gave it first support; D2 shows
  the cheap forms of it do not work and the ceiling that motivated it is
  partly circular.
- **The recurring mechanism is paper monopoly of the top-10** (7/10, 8/10 and
  10/10 in three of the five), with losses concentrated at knife-edge margins
  (0.00007, 0.00076, 0.00263). Whatever is tried next should target slot
  allocation at the k cutoff — but note R4 and R5 already rejected the obvious
  form of that, so it needs a genuinely different mechanism, not a third cap.
- **g148 is the one coverage gap with no cheap explanation** — its second gold
  chunk sits at fused rank 58 with a wide 0.01451 margin and BM25 never returns
  it at all. Nothing tested here moved it, and it is also the only target `k=20`
  does not rescue.
- **`k` becomes a Phase 4 question.** The k=20 arithmetic above says most of
  this type's failures are cutoff artefacts, not retrieval failures. That
  decision belongs with the generation step's context budget, measured on
  answer quality against cost and latency — not settled here.

---

## D1 — 2026-08-14 — Diagnostic: g080 unreachable, g084 lost in fusion

**Commands:** ad-hoc probes against the live `evalv1` index (channel calls,
`fuse()` counterfactuals, a corpus-wide anchor scan), plus re-analysis of the
stored R2–R5 reports. No harness run; no report file written.
**Cost:** 4 live Cohere embed calls (~$0.00002), user-authorized. No rerank calls.

### State at time of run

| | |
|---|---|
| Golden set | 150 questions, human-verified — identical to R2–R5 |
| Scored | **none** — this entry produces no recall/NDCG over the dataset |
| Corpus | `evalv1`, verified live: 1,518 indexed chunks / 638 claims / 1,624 entities |
| Code | commit `ff1a9c9`, **unmodified** — no source file was changed |
| Config | k=10, over-fetch 60, entity weight 0.1, gate `(dense_chunks, dense_claims)` |

### Comparable to

**Nothing — and it supersedes nothing.** This is a diagnostic entry, not a
run. Every per-question number quoted below is either read from the stored
R2/R3/R4/R5 reports or recomputed live against the same index, code and
config those runs used. It changes no headline figure.

---

### g080 — root cause: the question, not the retriever

R3 logged g080 as unreachable by every channel and left it unexplained. It is
now explained, and the cause is in the golden set.

**Not an indexing gap.** Both gold chunks are present in `dr-chunks-evalv1`
with vectors: `2607.26952` abstract (p1, 199 words) and `2607.27191` sec 4.4
(p11–12, 379 words). Each evidence quote resolves to exactly one chunk. This
matters because `relevant_chunk_ids` is computed from **Postgres**, not the
index — a chunk can count as gold while being absent from OpenSearch (ADR
0003 excludes 106 bibliography chunks that way). Checked explicitly here;
both are indexed.

**The query shares no content with its own evidence.** After stopwording,
g080's question has three content words — `llm`, `papers`, `weakness`. Term
counts inside the gold chunks:

| gold chunk | `llm` | `weakness` |
|---|---|---|
| 2607.26952 (abstract) | 0 | 0 |
| 2607.27191 (sec 4.4) | 0 | 0 |

BM25 cannot match on absent terms. What the channels do instead confirms the
index is healthy and the query is empty: **bm25** returns a full 60 hits with
rank 0 at `2607.27191::4-7-wefound-no-significant-reward-hacking` — the right
paper, the wrong section — and **entities returns 0 hits**, no query n-gram
matching any entity key.

g080 is a corpus-level meta-question (*"Two of these papers…"*) whose referent
no retriever receives, and whose discriminating content — credit-card
reasoning, financial rules, AI peer review, the generator–verifier gap —
appears nowhere in the query string. **No retriever operating on this query
can reach this evidence.** The defect is in the question.

**Consequence for the numbers:** g080 is the only unreachable question, so it
alone holds reachability at 0.993 rather than 1.000. It contributes a hard 0.0
to `multi_paper`, which reads 0.569 with it and would read 0.621 without it.
**It is also not evidence about query decomposition** — decomposing g080
yields equally contentless sub-queries. Expect it to stay at 0.0 under any
decomposition experiment.

**Incidental finding — router false positive (real, currently inert).** The
router labels g080 `entity_anchored` because `LLM` matches `_ACRONYM_PATTERN`
in `_is_artefact_token` (`src/retrieval/router.py`), while the entity channel
returns zero hits for that same query. It changes nothing today:
`src/retrieval/search.py` runs all four channels regardless of route and only
`out_of_domain` short-circuits. It will misfire the moment Phase 4 routes
selectively. Any question mentioning LLM, RAG or BERT routes this way.

---

### g084 — root cause: a knife-edge fusion margin, not one lever

R3 recorded g084 at fused 0.000 with bm25 0.500 and dense_chunks 0.500 — the
pipeline scoring below its own best channel. Reproduced live.

**Gold is found by three channels and survives the gate.** The semantic gate
was the prime suspect and is **exonerated**: all 60 candidates pass it, and
both gold chunks are in `dense_chunks`' 60.

| gold chunk | bm25 | dense_chunks | dense_claims | entities | fused |
|---|---|---|---|---|---|
| `2607.27136` KAMR abstract | 26 | 7 | — | 16 | **10** |
| `2607.26470` CMT-RAG abstract | 4 | 33 | — | — | **13** |

**The cutoff is decided by 0.00007.** Fused rank 9 scores 0.02757; the KAMR
gold at rank 10 scores 0.02750 — a 0.25% difference. The top-10 is **8 of 10
chunks from KAMR**: its introduction, related work, task definition,
inference and additional-experiments sections evict its own abstract. Each
entity-channel hit contributes ~0.0013 to the fused score, roughly **19× the
margin that decides the outcome**, and the entity channel's 17 hits are all
tied at score 0.383 — so its rank order, and therefore this question's
result, is insertion-order arbitrary.

**No tested configuration retrieves both gold chunks. The ceiling is 0.500.**

| lever | result |
|---|---|
| entity weight 0.1 (**shipped**) | **0.000** |
| entity weight 0.0 / 0.05 / 0.3 / 1.0 | 0.500 (all four) |
| entity channel removed entirely | 0.500 |
| RRF `k` = 20, 30 | 0.500 |
| RRF `k` = 10, **60 (shipped)**, 120 | 0.000 |
| per-paper cap 2 / 3 / 5 | 0.500 — but KAMR gold **drops out**, CMT-RAG enters |

Three unrelated parameters flip the outcome non-monotonically, and the
shipped values of two of them land on the wrong side. **This is noise, not a
bug with a fix.** Tuning `entity_weight` or the RRF constant to recover g084
would be fitting the dev set, which R4's dev-set discipline forbids.

**Correction to an earlier reading of R4.** R4's per-paper cap is the only
config where g084 scores 0.500, which invited the reading that the cap
*rescued* the crowded-out gold. It does not — it **swaps** which gold
survives. KAMR's abstract sits at fused rank 10, making it roughly the 9th
KAMR chunk, so a cap of 3 deletes it before relevance scoring. That is
exactly R4's recorded lesson, now observed at chunk level.

**What survives every config:** the top-10 holds 8–9 chunks from a single
paper. Two gold abstracts from two papers never co-occur, and the only lever
that promotes one demotes the other. This is the first **empirical** support
for query decomposition, which R5 recorded as a plausible direction with no
evidence behind it: running each sub-question separately is the only route by
which both abstracts could occupy the result set, since every
within-one-ranking lever tops out at 0.500.

---

### Corpus-wide anchor scan (free, no API)

To test whether g080 represents a class, each scored question was given a
**weakest-anchor IDF**: over its weakest gold chunk, the highest IDF among
terms shared with the question. IDF replaces a hand-written stopword list, so
corpus-generic words score low on their own merits. IDF was computed over
1,639 Postgres chunks against 1,518 indexed; the gap reconciles exactly as 15
sandbox-corpus chunks + 106 ADR-0003 bibliography exclusions.

**The metric predicts recall:** Pearson r = **+0.420** against fused recall,
**+0.429** against bm25, **+0.256** against dense_chunks — strongest for the
lexical channel, which is the sanity check passing. Questions with anchor
< 3.0 average **0.537** fused recall (n=9); those ≥ 3.0 average **0.969**
(n=127).

**`multi_paper` is systematically anchor-poor** — mean 2.87 against 4.24–4.87
for every other type, min 0.02. The four lowest-anchor questions in the entire
golden set are all `multi_paper`, and the type fills 4 of the 9 sub-3.0 slots
while being 8.8% of the set. Two are worse-anchored than g080 by any measure:
**g088** (only shared term `the`, IDF 0.02) and **g087** (`with`, 0.23), both
capped at 0.500 fused.

**Stated limits of the metric.** It has false positives — g063 (2.25) and
g010 (2.85) both score 1.000 because dense rescues them — and one notable
false negative: **g080 itself ranks 21st at 3.38**, because its only shared
term is the verb *"find"*. IDF rewards rare function words, not topical
specificity. Screening heuristic, not a verdict.

### Gold retrieved, then lost — measured across the set

Comparing each question's fused recall against its own best single channel
(a per-query oracle, not a selectable strategy):

| run | questions below best channel | recall lost | of which `multi_paper` |
|---|---|---|---|
| R3 (Cohere) | 5 | 2.17 | 3 |
| R2 (identity) | 9 | 5.67 | 3 |

Mean oracle best-channel recall is 0.945 against fused 0.940, so the pipeline
captures 99.5% of it — **this is not a broken pipeline**. It also
independently re-confirms the reranker, which more than halves the loss. But
it concentrates: 3 of 12 `multi_paper` questions have gold in a channel's
top-10 and lose it downstream (g084, g034, g017).

### What this entry does and does not license

- **Does not support deleting the entity channel.** g084 was probed as
  evidence for that pending ADR and does not serve as such — two of the four
  alternative weights work equally well. The decision still rests on the
  n=136 recall of 0.260 from R3.
- **Does not license tuning** `entity_weight` or the RRF constant on these
  results. Both flip g084 non-monotonically at margins of ~1e-4.
- **Closes R3's g080 anomaly** — cause identified, in the golden set. The
  disposition of g080, g087 and g088 is the user's, per golden-set authority.
- **Leaves open** whether the knife-edge is general. The stored reports record
  recall only, not scores or ranks, so counting how many questions sit within
  a hair of the k=10 cutoff needs the eval instrumented to emit gold's fused
  rank and its margin to the cutoff, plus one re-run (free with identity).

---

## R5 — 2026-08-10 — Rerank-then-diversify, cap 3, Cohere reranker — REJECTED

**Command:** `uv run python scripts/eval_retrieval.py --corpus evalv1 --k 10 --reranker cohere_bedrock`
**Report:** `notebooks/phase3_retrieval/retrieval_eval_cohere_diversify.json`
**Cost:** ~$0.15 (136 rerank calls at 60 docs each, plus query embeddings). Live Bedrock, user-authorized.

### State at time of run

| | |
|---|---|
| Golden set / corpus / config | identical to R3 |
| Code | **uncommitted working tree on `13b5236`**: reranker scores all 60 fused candidates (`top_n = len(fused)`), then greedy selection with `diversify_cap=3` per paper and backfill from skipped hits |

### Hypothesis under test

R4's lesson applied: the pre-rerank cap died because it deleted gold before
relevance scoring, so constrain *selection* instead — every candidate gets a
relevance score, the per-paper cap only chooses among scored hits. Decision
rule pre-registered: accept iff `multi_paper` improves vs R3 without
material regression elsewhere; cap fixed at 3, no sweep.

### Results — paired against R3 (only the selection stage differs)

| | R3 | R5 |
|---|---|---|
| **fused recall@10** | **0.940** | **0.875** |
| fused NDCG | 0.817 | 0.792 |

| type | n | R3 | R5 |
|---|---|---|---|
| factual_single | 33 | 1.000 | 0.970 |
| entity_anchored | 18 | 1.000 | 0.944 |
| negation | 21 | 0.976 | 0.929 |
| definitional | 30 | 0.967 | 0.867 |
| computable | 22 | 0.932 | 0.788 |
| multi_paper | 12 | 0.569 | 0.597 |

Per-question: **10 worse, 1 better** (g017, 0.333 → 0.667), 125 unchanged.
Nine of the ten regressions fell from 1.000, four of them in `computable`.

### Verdict

**Rejected on the pre-registered rule: `multi_paper` gained +0.028 (about a
third of one question at n=12) at the cost of 10 whole questions
elsewhere.** The mechanism survives relevance scoring: on the regressed
questions the reranker places three or more same-paper chunks *above* the
gold chunk, so the selection cap skips gold exactly as the pre-rerank cap
did. The R4 lesson generalizes — within-paper order is unreliable under
*both* RRF and cross-encoder scoring, so **per-paper caps are the wrong
lever for `multi_paper` entirely**, at any stage of the pipeline. The
plausible right lever is query decomposition: a two-paper question becomes
two sub-queries, each retrieved on its own merits — an architecture change,
not a selection tweak; not built, not measured, recorded here as the
surviving direction.

Also confirmed live: the new exclusion buckets from `13b5236` — g038 now
prints as `excluded, no evidence by design`, `evidence_unmatched` empty.

---

## R4 — 2026-08-09 — Per-paper cap 3, identity reranker — REJECTED

**Command:** `uv run python scripts/eval_retrieval.py --corpus evalv1 --k 10 --reranker identity`
**Report:** `notebooks/phase3_retrieval/retrieval_eval_identity_cap3.json`
**Cost:** query embeddings only (136 embed calls, negligible). Live Bedrock, user-authorized.

### State at time of run

| | |
|---|---|
| Golden set | 150 questions, human-verified — identical to R2/R3 |
| Scored | 136 — same exclusions as R2/R3 |
| Corpus | `evalv1` — identical to R2/R3 |
| Code | **uncommitted working tree on `658cb5e`**: `cap_per_paper` filter between fusion and rerank, `per_paper_cap=3` (chunks and claims share a paper's slots) |
| Config | k=10, over-fetch 60 — identical to R2, plus the cap |

### Hypothesis under test

R3 finding 2: `multi_paper` recall 0.569 because RRF lets one strong paper
flood the shortlist. The cap skips any fused hit whose paper already has 3
accepted, so the reranker sees more papers. Decision rule fixed **before**
the run (see "dev-set discipline" below): accept iff `multi_paper` improves
without denting `factual_single`; no sweeping the cap value.

### Results — paired against R2 (identity, no cap; only the cap differs)

| | R2 recall@10 | R4 recall@10 |
|---|---|---|
| **fused** | **0.907** | **0.719** |
| fused NDCG | 0.681 | 0.613 |

| type | n | R2 | R4 |
|---|---|---|---|
| factual_single | 33 | 1.000 | 0.848 |
| negation | 21 | 0.976 | 0.643 |
| entity_anchored | 18 | 0.944 | 0.750 |
| definitional | 30 | 0.917 | 0.683 |
| computable | 22 | 0.871 | 0.773 |
| multi_paper | 12 | 0.514 | 0.444 |

Per-question: **30 worse, 1 better** (g084, 0.0 → 0.5), 105 unchanged.
Channels and reachability identical to R2, as they must be — the cap sits
after fusion.

### Verdict

**Rejected on the pre-registered rule — every type regressed, including the
one the cap was built for.** The mechanism is the one flagged in review
before the run: a gold chunk ranked 4th-or-lower among its own paper's hits
in RRF order is deleted from the candidate pool before anything
relevance-aware sees it. Within-paper RRF rank is a poor proxy for
relevance, so the cap trades gold for diversity. Any future diversity
intervention must constrain *selection after relevance scoring*
(rerank-then-diversify), never filter candidates before it.

### Dev-set discipline — applies to this and all golden-set numbers

The golden set has been used to tune `entity_weight` (R1 sweep), the gate
config, and now to accept/reject this cap. It is functioning as a **dev
set**: its numbers measure fit to these 150 questions, not held-out
generalization. This entry's decision rule (single pre-registered binary
comparison, no value sweep) is the standing mitigation. A frozen held-out
split is pending — see `doc/project-status.md`, Decisions pending.

### Correction to R3's g038 anomaly

R3 recorded that g038 "passes the solvability audit, so the two checks
disagree". Wrong on inspection: g038 has an **empty evidence list by
design** (its answer is computed from corpus metadata; the SQL-over-metadata
route is unbuilt, and its notes say it is expected to fail until built). The
audit passes it vacuously (zero quotes to check) and the eval correctly
excludes it (recall over zero gold chunks is undefined). No disagreement,
no bug; both checks share one matcher (`quote_in_text`). The exclusion
stands until the metadata route exists.

---

## R3 — 2026-08-08 — Retrieval eval, Cohere reranker

**Command:** `uv run python scripts/eval_retrieval.py --corpus evalv1 --k 10 --reranker cohere_bedrock`
**Report:** `notebooks/phase3_retrieval/retrieval_eval.json`
**Cost:** ~$0.15 (136 rerank calls at 60 docs each, plus query embeddings). Live Bedrock, user-authorized.

### State at time of run

| | |
|---|---|
| Golden set | 150 questions, **all human-verified** (flags cleared same day, commit `658cb5e`) |
| Scored | 136 — excludes 8 `unanswerable` + 4 `out_of_domain` (no evidence by design), and g038 (see anomalies) |
| Corpus | `evalv1`, 54 papers / 1,518 indexed chunks / 638 claims / 1,624 entities |
| Code | commit `658cb5e`, no retrieval change since R1 |
| Config | k=10, over-fetch 60, entity weight 0.1, gate `(dense_chunks, dense_claims)` |
| Models | embed `global.cohere.embed-v4:0` (ap-south-1), rerank `cohere.rerank-v3-5:0` (eu-central-1) |

### Results

| channel | recall@10 | NDCG@10 |
|---|---|---|
| bm25 | 0.838 | 0.650 |
| dense_chunks | 0.858 | 0.675 |
| entities | 0.260 | 0.111 |
| dense_claims | n/a — measured separately | |
| **fused + rerank** | **0.940** | **0.817** |

Reachability **0.993** before rerank.
Claims channel: relevant claim surfaced on **19 of the 21** questions that have one.

**Recall by question type** — the reason this run exists:

| type | n | recall@10 |
|---|---|---|
| factual_single | 33 | 1.000 |
| negation | 21 | 0.976 |
| definitional | 30 | 0.967 |
| entity_anchored | 18 | 1.000 |
| computable | 22 | 0.932 |
| **multi_paper** | **12** | **0.569** |

### Comparable to

- **R2 — yes, directly.** Same dataset, same code, same config; only the
  reranker differs. This pair is the reranker's paired comparison.
- **R1 — NO.** R1 scored 29 questions, R3 scores 136. Nothing in the
  retriever changed between them; the instrument did. See "Why the numbers
  fell" below before reading any drop as a regression.

### Findings

**1. The reranker earns its place.** +0.033 recall, **+0.136 NDCG** over
identity fusion at n=136. Per-question: better on 56, worse on 14, unchanged
on 66. At n=29 this effect was suggestive; at n=136 it is decisive. This
supports an ADR.

**2. `multi_paper` is the standing weakness — 0.569 recall against 0.93–1.00
everywhere else.** Invisible before: R1 had 2 such questions, R3 has 12. Four
of the twelve score at or below 0.33 (g017, g080, g084, g108). The plausible
mechanism is structural — these need chunks from *two* papers, and RRF
rewards documents that several channels agree on, which favours a single
strong paper over one chunk from each of two. Not yet diagnosed; do not
treat that explanation as established.

**3. The entity channel weakened: 0.391 → 0.260 recall.** At n=136 this is a
readable signal rather than noise. This is the channel Phase 3 explicitly
deferred deleting until the golden set grew; the evidence to decide now
exists. No ADR written yet — the decision is the user's.

### Why the numbers fell vs R1

Every headline number is lower than R1 and **none of it is a regression** —
no retriever code changed. R1's 29 questions skewed toward `factual_single`,
which still scores a perfect 1.000 here. R3 deliberately added the hard
types (`multi_paper` 2→12, `computable` 9→22, `definitional` 9→30), so the
average fell. R1 was measuring an easier exam. The R3 numbers are the honest
ones; R1's were flattering.

### Anomalies — open, not explained

- **g080 unreachable.** No channel surfaces either of its 2 gold chunks
  inside the over-fetch of 60 — bm25, dense_chunks, dense_claims and
  entities all return 0.000. Reranking cannot recover it. This single
  question accounts for the entire drop in reachability from 1.000 to 0.993.
- **g038 excluded from scoring.** Reported as "no relevant chunk found": its
  evidence quote maps to no chunk, so it scores nothing rather than zero.
  It passes the solvability audit, so the two checks disagree — worth
  understanding, since a silently dropped question inflates every average.

---

## R2 — 2026-08-08 — Retrieval eval, identity reranker (baseline)

**Command:** `uv run python scripts/eval_retrieval.py --corpus evalv1 --k 10 --reranker identity`
**Report:** `notebooks/phase3_retrieval/retrieval_eval_identity.json`
**Cost:** free — identity reranker makes no API call; query embeddings only.

State identical to R3 except the reranker. Exists to isolate the reranker's
contribution; without it, R3's fused number cannot be attributed.

| channel | recall@10 | NDCG@10 |
|---|---|---|
| bm25 | 0.838 | 0.650 |
| dense_chunks | 0.858 | 0.675 |
| entities | 0.260 | 0.111 |
| **fused, no rerank** | **0.907** | **0.681** |

Reachability 0.993. Claims: 19 of 21.

**Comparable to:** R3 directly (the paired comparison). Not to R1.

---

## R1 — 2026-08-07 — Retrieval eval, first measurement

**Reports:** superseded by R2/R3; conclusions preserved in
`notebooks/phase3_retrieval/README.md`, which is marked stale.

| | |
|---|---|
| Golden set | ~39 questions, 29 scored |
| Corpus | `evalv1`, 54 papers / 1,518 chunks — same as R3 |
| Config | k=10, over-fetch 60 — same as R3 |

| channel | recall@10 | NDCG@10 |
|---|---|---|
| bm25 | 0.908 | 0.766 |
| dense_chunks | 0.856 | 0.684 |
| entities | 0.391 | 0.176 |
| **fused + rerank** | **0.977** | **0.912** |

Reachability 1.000.

**Comparable to:** nothing after it — superseded by R3 on a 4.7× larger
question set. Its diagnostic value survives and is worth keeping: the entity
channel scored 0.000 until it probed query n-grams instead of the whole
query; giving it full RRF weight then *cost* 0.035 recall, so a sweep set it
to 0.1; and the reranker's single regression (g033) traced to us withholding
section titles from it, not to the model.

**Caveat that applied then and still does:** at n=29 only large effects were
readable, which is why no channel was deleted on this evidence.

---

## Phase 1 — 2026-07-29 — Judge calibration + no-retrieval baseline

| | |
|---|---|
| Golden set | 33 questions, 29 scored |
| Rubric | v2 |
| Judge | `global.anthropic.claude-sonnet-4-6` |
| Generation | `global.anthropic.claude-haiku-4-5-20251001-v1:0` |

- **Judge–human agreement: 100% over 29 pairs.**
- **No-retrieval baseline: 0/29** — zero parametric leakage.

**Caveat, load-bearing:** the calibration set was *uniformly abstentions*.
100% agreement on a set where every correct verdict is the same verdict
demonstrates far less than the number suggests. Re-calibration on substantive
answers is still outstanding, and any later agreement figure is not
comparable to this one.

---

## Conventions for this file

- **One entry per run**, even when a run only confirms the previous one.
- **State the cost** of any run that spent money, and note that it was
  authorized.
- **`Comparable to` is mandatory.** If a run is not comparable to its
  predecessor, say so and say why in the same breath.
- **Record anomalies even when unexplained.** An unreachable question or a
  silently excluded one changes how every average should be read.
- **Never delete a superseded entry.** Mark it superseded; the history of
  what was believed and when is the point of the ledger.
