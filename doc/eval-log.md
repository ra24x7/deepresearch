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
| 2026-08-09 | R4 retrieval, per-paper cap 3, identity rerank | golden 150 (136 scored) | fused recall@10 **0.719** — cap rejected |
| 2026-08-08 | R3 retrieval, Cohere rerank | golden 150 (136 scored) | fused recall@10 **0.940**, NDCG **0.817** |
| 2026-08-08 | R2 retrieval, identity rerank | golden 150 (136 scored) | fused recall@10 0.907, NDCG 0.681 |
| 2026-08-07 | R1 retrieval, both rerankers | golden ~39 (29 scored) | fused recall@10 0.977, NDCG 0.912 |
| 2026-07-29 | Judge calibration + no-retrieval baseline | golden 33 (29 scored) | judge agreement 100%, baseline 0/29 |

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
