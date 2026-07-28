# ADR 0001 — Model choices for generation and judging

Date: 2026-07-28
Status: accepted
Evidence: `scripts/test_connections.py` discovery run in ap-south-1

## Decision

- **Generation + no-retrieval baseline:** `gpt-4o-mini` (OpenAI, direct API)
- **Judge:** Claude Sonnet 4.6 via Amazon Bedrock, model id
  `global.anthropic.claude-sonnet-4-6` (cross-region inference profile)
- Auth: OpenAI API key; Bedrock long-term API key (`AWS_BEARER_TOKEN_BEDROCK`)

## Why

- gpt-4o-mini: cheapest capable generator; same model as the predecessor
  project, so eval numbers are comparable across v1/v2 — improvements are
  attributable to retrieval architecture, not a model upgrade.
- Cross-provider judge (OpenAI generates, Claude judges) structurally removes
  LLM self-preference bias instead of correcting for it.
- Sonnet tier for judging: quality sufficient pending Phase 1 calibration;
  ~$1 per 100-question eval run.

## Rejected

- **Claude Sonnet 5 as judge** — visible in Bedrock but AccessDenied for this
  account; requires an AWS access grant. Revisit only if calibration shows
  Sonnet 4.6 disagreeing with human labels below the 90% bar.
- **First-party Anthropic API** — account already has Bedrock access; one
  fewer vendor account to manage.
- **Bare Bedrock model ids** (`anthropic.claude-sonnet-4-6`) — rejected by
  Bedrock for on-demand invocation; the `global.` inference profile is
  required.

## Revisit when

Phase 1 judge-human agreement < 90% at rubric v1+ → escalate judge tier.
