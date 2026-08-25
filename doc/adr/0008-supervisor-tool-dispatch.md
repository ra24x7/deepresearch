# ADR 0008 — Supervisor tools dispatch by rule, and ingestion needs consent

Date: 2026-08-25
Status: accepted
Evidence: **A1/A2** (`doc/eval-log.md`: of 7 `computable` failures only g020 and
g038 need a metadata route, "the other 5 being arithmetic-over-retrieved-text
that no new tool fixes"); a free scan of all 150 golden questions showing
`sql_metadata` fires on exactly those two and no others;
`src/tools/supervisor.py`, `src/tools/metadata.py`

## Decision

**Dispatch to tools from the rule-based route the guardrail already computed.
No LLM supervisor.**

- `dispatch(route)` maps `computable → sql_metadata`, `semantic` and
  `entity_anchored → search_papers`, `out_of_domain → None`.
- `sql_metadata` answers a fixed set of parameterized aggregates — corpus
  count, count by publication year, most frequent arXiv category — and returns
  `None` when no rule matches, so the query retrieves exactly as before.
- **No caller supplies SQL.** Not the user, not a model.
- `get_claims` and `search_papers` are plain reads.
- **`ingest_by_id` raises `ConfirmationRequired` unless passed `confirm=True`.**
- The graph gains a `metadata` node between guardrail and retrieve. When it
  answers, the query skips retrieval, generation and the judge entirely and
  costs nothing.

## Why

### An LLM supervisor has not earned a call per query

The same bar that keeps `retrieval/router.py` free of a model applies here: an
LLM router costs money on every query and cannot be justified before an eval
shows the rules failing. No eval shows that yet. The rules can be replaced the
moment one does.

### The evidence says the tool surface needed is small

A1 classified the seven `computable` failures: **only g020 and g038 are corpus
aggregates**; the other five are arithmetic over retrieved text, which no
metadata query fixes. Both are answered exactly right from Postgres —
g020 "54 papers published in 2026" and g038 "cs.AI, in 27 papers", matching
their reference answers — and A2 got one wrong and abstained on the other.

Run over all 150 golden questions, `sql_metadata` fires on **exactly those two
and nothing else**. Falling through is the designed failure mode: inventing an
aggregate for a question that is not one would be worse than retrieving.

### Ingestion is a paid write reachable from a query

`ingest_by_id` composes parse → enrich → embed. Enrichment alone is
$0.0079/paper, and the write mutates the corpus every eval number is measured
against. A query path that can trigger it without consent is a way to spend
money and invalidate a frozen snapshot by accident. The confirmation flag makes
that impossible to do implicitly, and the refusal names the paper it declined.

## Trade-offs accepted

- **Three hand-written regexes decide what counts as a corpus aggregate.** They
  fire correctly on 150 questions, which is 150 questions, not a guarantee. A
  question phrased outside them falls through to retrieval and answers no worse
  than today.
- **Category counting happens in Python, not SQL.** `categories` is a JSON
  array; unnesting it portably costs more than a `Counter` over 54 rows. This
  stops being right somewhere north of a few thousand papers.
- **The metadata answer is not judged against retrieved evidence.** It has no
  chunks and no citations, so Phase 5's attribution work will have to treat it
  as its own case rather than a degenerate retrieval.
- **`get_claims` is built and dispatched to by nothing.** Claims left the
  retrieval path in ADR 0005 and are kept as a product surface; this is the
  read for that surface, and no route reaches it yet.
- **Corpus aggregates rot silently.** g020 already sat stale at "4 papers"
  while the corpus grew to 54. Answering from live metadata fixes the *answer*
  and does nothing for the 24 `computable` reference answers that still hold
  frozen numbers.
