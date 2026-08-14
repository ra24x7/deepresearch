# ADR 0005 — The claims channel: keep, delete, or re-scope

Date: 2026-08-14
Status: accepted
Evidence: **R6 claims ablation at n=136** (`doc/eval-log.md`, ±0.0000); R3
(n=136); D1 (semantic-gate mechanics); D2
(claims absent from all five probed failures); commit `4f1a95f` (full-corpus
enrichment, $0.389); `src/retrieval/fusion.py`, `src/retrieval/channels/dense.py`

## Decision

**Remove `dense_claims` from the retrieval path; keep claims indexed and
queryable (option B).**

- `src/retrieval/search.py` no longer queries or fuses the claims channel.
- `scripts/eval_retrieval.py` still *retrieves* claims and reports
  `claim_found` on its own terms, but excludes them from `fuse()` — the eval
  must mirror the shipped system, and it now does.
- `scripts/sweep_fusion_weights.py` mirrors the same change.
- `fuse()` itself is **unchanged**. Its `gate_channels` default still names
  `dense_claims`, which is harmless when no such channel is supplied, and its
  docstring warns that editing the gate would "silently discard the whole
  channel rather than merely down-rank it". Removal is therefore explicit at
  the call site, exactly as that warning asks.
- The 638 claims stay in `dr-claims-evalv1`, `search_dense_claims()` stays,
  and enrichment continues at ingest.

## Why

This channel is measured differently from the others, and that difference is
the whole decision.

### It cannot contribute to the metric the other channels are judged on

`search_dense_claims` returns hits whose `doc_id` is a **`claim_hash`**
(`src/retrieval/channels/dense.py`). Gold relevance is a set of **`chunk_id`s**
(`relevant_chunk_ids`). The two id spaces never intersect, so `dense_claims`
can never add chunk recall — by construction, not by weakness. R3 records it as
"n/a — measured separately", and the eval deliberately scores claims apart,
with the reason in `scripts/eval_retrieval.py`: counting an unfound claim as a
miss "would punish 25 questions to measure 4".

### On its own terms it works

R3: a relevant claim surfaced on **19 of the 21 questions that have one** — a
0.905 hit rate. The channel does what it was built to do.

But note the denominator. **21 of 136 questions have a relevant claim at all.**
The channel's applicability is bounded by what the questions ask, not by how
much of the corpus is enriched — the lesson already recorded in `4f1a95f`,
where enriching 49 more papers "bought no eval signal" because the questions
still targeted the same papers.

### D2 found it silent on every failure investigated

Across all five genuine `multi_paper` failures (g034, g017, g084, g148, g108),
`dense_claims` returned **no gold chunk in any position** — expected given the
id-space argument above, but worth recording: the channel contributed nothing
to the questions that most needed help.

### It does hold a structural role in the gate

`fuse()` gates on `("dense_chunks", "dense_claims")`. D1 established what that
means in practice: since claims key on `claim_hash`, for **chunks** the
effective gate is `dense_chunks` alone. The docstring already anticipates this
— claims are in the gate tuple so that excluding them would not "silently
discard the whole channel rather than merely down-rank it."

### The open question, now measured (R6): the channel is inert for chunk retrieval

Claim documents pass the gate and enter the fused ranking, so they *can* occupy
top-k slots that chunks would otherwise take. R6 measured how often, and what
removing them does, across all 136 scored questions:

| | |
|---|---|
| claim docs in the fused top-10 | **15 slots of 1,360 (1.10%)** |
| questions with ≥1 claim in the top-10 | **8 of 136** |
| chunk recall@10 **with** `dense_claims` in fusion | 0.9069 (NDCG 0.6814) |
| chunk recall@10 **without** `dense_claims` in fusion | **0.9069 (NDCG 0.6814)** |
| delta | **+0.0000 recall, +0.0000 NDCG** |

Identical to four decimal places, and **every question type is unchanged**.

So the channel is **neither helping nor hurting chunk retrieval**. The 15 slots
it takes displace only non-gold chunks. This removes the one argument that
would have forced its removal — it is not stealing anything — and equally
removes any retrieval-side argument for keeping it in fusion.

## Options

**A — Keep as-is.** Costs nothing measurable (R6: ±0.0000), answers 19 of 21
applicable questions, write-path cost already sunk. *Accepts:* a channel in the
fusion path with no demonstrated retrieval benefit — carried on the strength of
the golden set under-sampling claim questions (21 of 136), not on a number.

**B — Remove `dense_claims` from fusion, keep claims indexed as a product
surface.** Claims stay queryable for "what does this paper contribute?" but stop
entering the retrieval ranking. R6 says this costs **exactly zero** chunk
recall and NDCG. *Accepts:* the 8 questions where a claim currently reaches the
top-10 lose it; the metric cannot see whether that ever mattered. Also requires
care with `fuse()`'s gate tuple — the docstring warns that dropping claims from
the gate would "silently discard the whole channel rather than merely down-rank
it", so removal must be explicit, not by gate edit.

**C — Delete the channel and stop paying for enrichment.** Saves $0.0079/paper
on every future ingest. *Accepts:* discarding 638 extracted claims and a
capability the golden set under-represents but a real product might use
heavily. The write path would need ADR 0002-style revisiting if reinstated.

**Recommendation is not made here.** My read, offered as a read: R6 makes this
a *product* decision rather than a retrieval one — retrieval is provably
indifferent (±0.0000). So the question is only whether claims earn their place
as a product capability. (C) is the hardest to reverse and rests on a golden set
that under-samples the very questions claims serve; (B) is the honest middle,
since it keeps the capability while removing an unmeasured component from the
retrieval path.

## Trade-offs accepted

- **The 8 questions where a claim currently reaches the top-10 lose it.** The
  metric cannot see whether that ever helped an answer, because claims are
  scored separately by design. We are removing something whose benefit is
  unmeasurable rather than measured-zero.
- **We keep paying $0.0079/paper for enrichment** without a retrieval
  justification. Accepted: the golden set has 21 of 136 questions where a claim
  applies, which is too thin to conclude claims lack product value, and the
  write path is expensive to reinstate.
- **A capability now sits outside the measured path.** Nothing in the eval
  harness will notice if the claims index rots — no golden question fails when
  claims degrade. If claims become a product surface, they need their own
  measurement.
- **`fuse()` keeps a stale-looking default.** `gate_channels` still names a
  channel the orchestrator never passes. Left deliberately, per the docstring's
  own warning; a future reader may find it confusing.

## What this bought

Beyond the ranking change, the orchestrator now makes **one query embedding per
search instead of two** — `search_dense_chunks` and `search_dense_claims` each
called `provider.embed_query()` independently. That halves the per-query
embedding cost, which matters for Phase 4's cost-per-query budget.
