# Phase 3 — Staged Retrieval Engine

Read path: `route → BM25 + dense(chunks) + dense(claims) + entities → RRF
fusion behind the semantic gate → cross-encoder rerank → top_k`.

## What was measured

29 answerable golden questions, `k=10`, over-fetch 60, corpus `evalv1`
(54 papers / 1,518 indexed chunks). Artifacts: `retrieval_eval.json`
(current), `retrieval_eval_identity.json` (no-rerank baseline),
`fusion_weight_sweep.json`.

| channel | recall@10 | NDCG@10 |
|---|---|---|
| bm25 | 0.908 | 0.766 |
| dense_chunks | 0.856 | 0.684 |
| entities | 0.391 | 0.176 |
| dense_claims | measured separately — see below | |
| **fused + Cohere rerank** | **0.977** | **0.912** |

**Reachability 1.000.** Every gold chunk was surfaced by some channel inside
the over-fetch. Reachability and recall@10 are different failures with
different fixes: a chunk no channel returned is lost before the reranker sees
the shortlist, and no amount of reranking recovers it. The ceiling is not
binding here, so ranking — not retrieval breadth — was the thing to improve.

## How it got there

Each number below came from fixing something the eval exposed, not from tuning
toward a target.

**The entity channel scored 0.000 because it matched the whole query.** It
term-matched the entire question against `entity_key`, so `"A-RAG"` returned 10
hits and `"What three retrieval tools does the A-RAG framework provide?"`
returned none. Its unit tests passed because they all used bare entity names.
Probing the query's n-grams instead took it to 0.391.

**Fixing it made fused retrieval worse** — 0.931 → 0.902. RRF gave a chunk that
merely *mentions* an entity a full rank-0 contribution, outweighing a chunk
that dense ranked 5th and actually answered. The semantic gate blocks
introduction, not reordering, and the reordering was bad. A weight sweep over
cached retrievals (channels run once, each config scored by re-fusing) found
the shape:

| entity weight | recall@10 | NDCG@10 |
|---|---|---|
| 0.00 | 0.931 | 0.745 |
| **0.10** | **0.966** | **0.751** |
| 0.25 | 0.937 | 0.737 |
| 1.00 | 0.902 | 0.740 |

Entity matches are a tiebreaker among candidates the semantic channels already
found; they do not get a vote. Default set to 0.1.

**The reranker's single regression was our fault, not the model's.** Cohere
rerank lifted NDCG 0.751 → 0.901, better on 10 questions, worse on 3. Tracing
the worst (g033, 1.000 → 0.387) showed the gold chunk falling from rank 1 to 5
while four chunks *from the same paper* passed it — right document, wrong
section. The question asks about "APS-RAG's troubleshooting knowledge graph";
the gold chunk's body never writes "APS-RAG", only "The graph contains 96,517
nodes and 84,222 edges". Its heading — "F. A troubleshooting-oriented knowledge
graph" — anchors it exactly, and we were not sending headings to the reranker.
With them: g033 back to rank 1, NDCG 0.912, regressions down to 2.

Investigating the loser was worth more than celebrating the average.

## The claims channel

`dense_claims` reads `n/a` against chunk relevance by construction: relevance
is defined over chunk ids and claims carry `claim_hash`. Measured on its own
terms — a claim is relevant when it *states the fact asked for*, matched
against the evidence quote and reference answer — **it surfaced the relevant
claim on 4 of the 4 questions that have one.**

Merging claims into the chunk relevance set was tried first and dropped fused
recall 0.966 → 0.891: a question whose chunk already answers it was penalised
for not *also* retrieving its claim. 25 questions distorted to measure 4.

The channel works; it applies narrowly, because only **6 of 54 papers are
enriched**. Whether it earns its keep at full coverage is untested — enriching
the remaining 48 costs roughly $0.38 and is the experiment that would settle it.

## Caveats that qualify all of the above

- **n=29 answerable questions.** Only large effects are readable. The
  reranker's +0.15 NDCG qualifies; the entity channel's +0.035 recall does
  not. **No ADR deletes a channel on this evidence** — these numbers are for
  diagnosis and tuning.
- **Per-type breakdowns rest on 3 and 2 questions** (`entity_anchored`,
  `multi_paper`). Both remaining reranker regressions fall in those types,
  which is exactly where the sample is thinnest.
- **BM25 out-scoring dense may be an artifact of question construction.**
  Mean question↔evidence lexical overlap is 0.30, with three questions above
  0.50 — BM25 is advantaged by how the questions were written.
- **The `computable` route retrieves semantically.** The SQL-over-Postgres path
  in the architecture is not built; those questions currently fall through.
- **Reachability 1.000 is measured against a 54-paper corpus.** It will not
  survive a 500-paper one unchanged, and the over-fetch of 60 should be
  re-examined then.
