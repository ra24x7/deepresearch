# ADR 0004 — The entity channel: keep, delete, or repair

Date: 2026-08-14
Status: accepted
Evidence: **R6 weight sweep at n=136** (`doc/eval-log.md`); R3 (n=136); R1 weight
sweep (`notebooks/phase3_retrieval/fusion_weight_sweep.json`, n=29,
**superseded**); D1 forensics on g080 and g084; commit `4f1a95f` (full-corpus
enrichment effect)

## Decision

**Keep the entity channel, at `entity_weight = 0.1` (option A).** No code
changes.

Two defects are recorded here as known issues, deferred rather than dismissed:

1. **Tied scores.** Every hit in an observed query came back at exactly 0.383,
   so RRF — which fuses by rank — orders them by insertion, i.e. arbitrarily.
   The cause is **inferred, not verified**: `terms` queries return a constant
   `_score` in OpenSearch, which would make `_damped()` a constant whenever the
   matched entities share a `link_count`. Verify before fixing.
2. **Generic entities.** The extractor emits ordinary words as entities —
   `joint` appears in 32 papers, alongside `coverage`, `accuracy`, `precision`.
   A `link_count` ceiling already exists in `search_entities` and is off by
   default.

Fix both when `multi_paper` work resumes (parked by `doc/eval-log.md` D2), then
re-run the free sweep. Do not fix them piecemeal without re-measuring.

## Why

Phase 3's exit criterion is "each retriever proves added recall or is deleted
(ADR either way)". This is the channel that criterion was written for.

### What the channel scores on its own

| run | n | recall@10 | NDCG@10 |
|---|---|---|---|
| R1 | 29 | 0.391 | 0.176 |
| **R3** | **136** | **0.260** | **0.111** |

Every other channel sits far above this: bm25 0.838, dense_chunks 0.858 at
n=136. The channel weakened as the question set grew and got harder, which is
what a channel with a narrow competence does.

### The sweep, re-run at n=136 (R6) — the shipped weight survives

The weight that set `entity_weight = 0.1` came from a sweep on **29 questions**
(0.0 → 0.9310 recall, 0.1 → 0.9655, i.e. +0.0345). R3 superseded that question
set, so R6 repeated the sweep at n=136, identity reranker:

| entity weight | recall@10 | NDCG@10 |
|---|---|---|
| 0.0 (off) | 0.8958 | **0.6855** |
| 0.05 | 0.9032 | 0.6844 |
| **0.1 (shipped)** | **0.9069** | 0.6814 |
| 0.25 | 0.8971 | 0.6756 |
| 0.5 | 0.8750 | 0.6689 |
| 1.0 | 0.8750 | 0.6607 |

**0.1 is confirmed as the recall optimum on the current instrument** — but the
effect is a third of what n=29 claimed: **+0.0111 recall, not +0.0345**, at a
cost of 0.0041 NDCG. NDCG falls monotonically as the weight rises, so the
channel always costs ranking quality; only recall pays it back, and only in a
narrow band around 0.1.

**Where the gain comes from, and what it costs** (weight 0.0 → 0.1):

| type | 0.0 | 0.1 | delta |
|---|---|---|---|
| factual_single | 0.970 | 1.000 | **+0.030** |
| negation | 0.929 | 0.976 | **+0.047** |
| **multi_paper** | 0.556 | 0.514 | **−0.042** |
| computable / definitional / entity_anchored | unchanged | | |

The channel buys `factual_single` and `negation` and **pays for it in
`multi_paper`** — the type already measured as the weakest. Notably it does
*not* move `entity_anchored`, the type named after it, which stays 0.944 at
both weights.

### Enrichment made it noisier, measurably

Full-corpus enrichment (`4f1a95f`) multiplied entities sevenfold, to 1,624. On
the same n=29 set, NDCG at weight 0.1 fell **0.751 → 0.737** while recall held.
The cause is visible in the data: the extractor emits generic words as metrics
— `joint` appears as an entity in 32 papers, alongside `coverage`, `accuracy`,
`precision`. Damping suppresses their score but they still enter fusion and
reorder results.

### Its internal ordering is arbitrary, and that decides questions

D1 measured this directly on g084. The channel returned **17 hits, every one
scored 0.383** — identical. RRF fuses by rank, so with all scores tied the rank
order is insertion order, i.e. arbitrary. Each entity hit contributes ~0.0013
to the fused score, and the margin that decided whether g084's gold chunk made
the top-10 was **0.00007** — roughly **19× smaller** than one arbitrary hit's
contribution.

D1 also showed the shipped weight of 0.1 is the *only* one of five tested
(0.0, 0.05, 0.1, 0.3, 1.0) that fails g084; the other four all score 0.500.

### And it disagrees with the router about its own competence

The router classifies any question mentioning an acronym as `entity_anchored`
(`_is_artefact_token`). On g080 it did exactly that — and the entity channel
then returned **zero hits** for the same query. The router's notion of "this is
an entity question" and the entity index do not agree.

## Options

**A — Keep at weight 0.1.** R6 confirms it is the recall optimum at n=136:
+0.0111 recall over off. *Accepts:* 0.0041 NDCG, a 0.042 loss on `multi_paper`
(the weakest type), and arbitrary tie-ordering continuing to decide knife-edge
questions like g084.

**B — Delete the channel.** Buys +0.0041 NDCG, +0.042 `multi_paper` recall, one
fewer channel to maintain, and removes arbitrary reordering from every query.
*Accepts:* −0.0111 overall recall, concentrated as −0.030 `factual_single` and
−0.047 `negation`.

**C — Repair, then re-measure.** Two defects are named above and both are
fixable: break the score ties (entity `_score` is uniform for `terms` matches,
so damping collapses to a constant), and filter generic extractor output (the
`link_count` ceiling exists but is off by default). Then re-sweep. *Accepts:*
the decision is deferred; the re-sweep is free with the identity reranker.

**Recommendation is not made here.** My read, offered as a read: R6 turned this
from "justified by a superseded number" into a genuine, small trade —
**+0.0111 recall against −0.0041 NDCG and −0.042 on your worst type**. That is
close enough to a wash that (C) is attractive: both defects are real, neither
is speculative, and repairing them is the only path that could make the trade
clearly favourable rather than marginal. Note also that the channel does not
improve `entity_anchored` at all, which weakens the intuition that it has a
distinct competence worth preserving as-is.

## Trade-offs accepted

- **The gain is marginal and we are keeping it anyway.** +0.0111 recall is
  roughly 1.5 questions out of 136. It is positive and measured on the current
  instrument, which is the standard the exit criterion sets — but it is not a
  comfortable margin, and a future instrument could erase it.
- **We pay for it in `multi_paper`.** −0.042 on the weakest type (0.556 →
  0.514), to buy `factual_single` (+0.030) and `negation` (+0.047). Accepted
  because `multi_paper` is 12 questions of which D1 found 3 defective, so it is
  the least trustworthy number in the set to optimise against.
- **NDCG is worse at every non-zero weight.** −0.0041 at 0.1, falling
  monotonically thereafter. Ranking quality is being traded for coverage.
- **Arbitrary tie-ordering stays in the pipeline** and will keep deciding
  knife-edge questions, as it did on g084 where one entity hit's contribution
  was ~19× the 0.00007 margin. Accepted knowingly, with the fix deferred above.
- **The channel does not improve `entity_anchored`** (0.944 at both weights),
  so the name promises a competence the numbers do not show. Kept on aggregate
  recall alone.
- **This is dev-set evidence.** These 150 questions have now tuned
  `entity_weight` twice. The held-out split in `doc/project-status.md` remains
  pending, and this decision should be revisited when it exists.
