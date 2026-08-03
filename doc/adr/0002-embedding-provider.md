# ADR 0002 — Embeddings via Cohere Embed v4 on Bedrock, behind a provider interface

Date: 2026-08-03
Status: accepted
Evidence: `notebooks/phase2_ingestion/README.md` (Phase 2.5 run: 1,518 chunks +
45 claims embedded, ~$0.08); Service Quotas readout for `ap-south-1`

## Decision

- Embeddings: Cohere Embed v4 on Bedrock, `global.cohere.embed-v4:0`,
  `output_dimension` 1024, `embedding_types: ["float"]`.
- Asymmetric encoding: `input_type: search_document` for chunks/claims,
  `search_query` at query time.
- All callers depend on the `EmbeddingProvider` protocol
  (`src/ingestion/embeddings/base.py`), never on a concrete class. A
  deterministic `fake` provider implements the same protocol so the whole
  pipeline and test suite run without spending.
- The provider **choice** stays open: it is re-decided in Phase 3 against
  measured recall/NDCG, not now.

## Why

- One key, one bill: Bedrock already carries generation and judging (ADR 0001),
  so no new vendor account or secret.
- Asymmetric encoding is a measurable retrieval win and was the feature we
  verified Embed v4 supports before committing — it is the equivalent of the
  predecessor project's Jina `retrieval.passage`/`retrieval.query` tasks.
- Interface-first because the eval to decide the provider does not exist yet;
  building against the protocol keeps the decision cheap to revisit.

## Trade-offs accepted

- Not comparable to the predecessor's Jina-based numbers; a provider change
  would break comparability again and must be flagged in project-status.
- Account quota in `ap-south-1` is 200 requests/min but only **300k tokens/min**
  — a batch of 96 chunks is ~43k tokens, so throughput is token-bound, not
  request-bound. Handled by throttle-retry with backoff, not by pre-emptive
  pacing (Bedrock is paid capacity; the quota is the contract).
- Vectors currently live only in OpenSearch, so a re-index re-pays for
  embedding. Cheap at this corpus size; revisit before Phase 6's blue/green
  reindex, where the cost recurs by design.
