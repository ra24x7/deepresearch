# ADR 0006 — Langfuse for LLM traces, Logfire for infra spans

Date: 2026-08-18
Status: accepted — Langfuse implemented, Logfire pending
Evidence: vendor pricing and feature comparison, 2026-08-14; repository survey
showing no FastAPI, Redis or HTTP layer; `doc/eval-log.md` C1 (cost accounting
that nothing could cross-check) and A1 (a cost bug that survived three runs)

## Decision

Two observability tools with a split by concern, not by preference:

- **Langfuse** owns the LLM half — traces, generations, scores, user feedback,
  and eval datasets.
- **Logfire** owns infra — HTTP, SQL, and node timing spans.
- **Graph nodes are the one place both run**: a `@logfire.instrument` decorator
  on the outside, Langfuse spans on the inside.

`src/obs/tracing.py` implements the Langfuse half today and degrades to
`NullTracer` when credentials are absent. Logfire is not yet wired.

**Correlation is mandatory, not optional.** The Langfuse trace id is stamped
onto the Logfire root span and the OTel trace id into Langfuse trace metadata.

**Cost is never recomputed in a tracer.** `CostLedger` is the single source of
truth and its figure is passed through.

## Why

**This adds a tool the roadmap did not name.** `architecture.md` and the Phase
4 checklist name Langfuse only, so Logfire is a deliberate addition recorded
here rather than an unremarked drift.

**Langfuse alone satisfies Phase 4's exit criteria.** Token and cost tracking
per model call is a first-class Langfuse feature on every tier including free;
Logfire measures records, spans and metrics, leaving Bedrock cost mapping to
the caller. Phase 4 asks for cost-per-query, so Langfuse is the direct fit.

**Langfuse's datasets and scores map onto assets that already exist** — the
150-question golden set and the versioned judge rubric. Logfire has evals, but
the fit with what is already built is weaker.

**Logfire's value is scope, and that scope is mostly future.** It is
OpenTelemetry-native and could watch Airflow, OpenSearch, Postgres and a
service layer on one timeline. Today the project has none of the web tier its
division of labour assumes: a repository survey found **no FastAPI, no Redis,
no HTTP server**. What Logfire can instrument now is SQLAlchemy, OpenSearch
calls, boto3, and graph node timing. That is why it is sequenced second.

**Correlation is load-bearing because the split severs a question.** Latency
lands in Logfire and cost in Langfuse, so without a shared id nobody can ask
"which node was slow on the queries that cost the most" — the single most
useful question a cost-aware orchestrator can answer.

**Cost passes through rather than being recomputed** because a tracer that
prices independently can disagree with the eval report. C1 records what one
unexamined rate assumption cost this project in retracted numbers; A1 records a
cost bug that survived three runs. One source of truth, quoted everywhere.

**Hosted, not self-hosted.** Self-hosted Langfuse needs ClickHouse, Redis and
S3-compatible storage beside Postgres. The compose stack already runs
OpenSearch, Postgres and Airflow and has OOMed once at 50 papers. Traces here
are public arXiv content, so hosted is low-sensitivity.

## Trade-offs accepted

- **Two vendors, two SDKs, two dashboards** for a single-developer project with
  no production traffic. Justified only if the correlation actually gets built;
  without it this is two tools and no joint view.
- **Logfire is sequenced second and may stay unbuilt for a while.** Nothing
  breaks if it does — Langfuse alone meets Phase 4. The risk is that the split
  is recorded as decided while half of it is aspirational, which this status
  line is meant to prevent.
- **A hosted tracer means traces leave the machine.** Accepted because the
  content is public papers; it would need revisiting for private corpora.
- **The Langfuse client path is untestable without credentials.** Tests cover
  `NullTracer` and factory selection only; the real client is exercised the
  first time keys exist. Failing closed on a half-configured environment is the
  mitigation.
- **FastAPI and Redis instrumentation is inherited from a sibling project's
  architecture, not this one.** Those lines of the division of labour are
  forward-looking and will mean nothing until Phase 6 adds caching or a service
  layer.
