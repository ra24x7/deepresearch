# Spec — DeepResearch (working name)

> A production-grade RAG system for academic research, built from scratch.
> Successor to the arXiv Paper Curator course project — designed around the gaps
> that project left open: measurement, retrieval quality, and grounding.

## One-liner

Researchers ask questions in plain English and get precise, citation-backed
answers distilled from arXiv papers — with every claim traceable to the exact
passage that supports it.

## Who it's for

Researchers and engineers surveying a field: "what does the literature say
about X, and which paper says it?"

## Core product behaviors

### 1. Answerable questions

The system answers with inline, claim-level citations. Each sentence of the
answer maps to the specific chunk/claim that supports it — not a generic
"sources" list appended at the end.

### 2. Questions the corpus cannot answer

Abstention is a feature, not a failure:

- **Out-of-domain** (not about research): blocked by a guardrail before
  retrieval runs.
- **In-domain, not in corpus**: the system says so explicitly — "the corpus
  doesn't contain evidence for this; closest related work is X and Y" — and
  never answers from the LLM's parametric memory with fabricated citations.
- **Partially answerable**: partial answer with the gap made explicit.

### 3. Computable questions

"How many cs.CL papers were published last month?" is answered by generating
SQL against the metadata database, not by retrieving text chunks. Computable
answers are exact, not extracted.

## Question types the system must handle

These categories define the golden dataset. Every category has eval coverage.

| Type | Example | Correct behavior |
|---|---|---|
| Factual, single paper | "What rank does LoRA use in its experiments?" | Answer + citation to the passage |
| Multi-paper synthesis | "How do LoRA and QLoRA differ in memory use?" | Answer citing both papers |
| Entity-anchored | "What did the Kuzu paper benchmark against?" | Entity channel finds it even when embeddings miss the acronym |
| Computable | "How many diffusion papers this year?" | SQL over metadata, exact number |
| Unanswerable (in-domain) | "What does the GPT-6 paper report?" | Abstain, suggest nearest work |
| Out-of-domain | "Best pizza recipe?" | Guardrail block |

## Definition of "working"

The system is working when these are measured, not assumed:

1. **Retrieval matters**: removing retrieved context changes answers
   (context ablation). If answers barely move, retrieval is decorative —
   a real risk since arXiv overlaps the LLM's training data.
2. **Grounding survives perturbation**: swapping good evidence for wrong-paper
   chunks makes the system degrade or abstain, never bluff.
3. **Abstention is calibrated**: unanswerable golden questions get abstentions,
   answerable ones don't.
4. **Attribution is precise**: statement-level citation precision is measured
   on the golden set.
5. **Each retriever earns its place**: every retrieval channel demonstrably
   adds recall the others miss, or it gets deleted (recorded in an ADR).

Numeric targets per phase live in [project-status.md](project-status.md).
The judge rubric is version-controlled — reported accuracy is a function of
dataset + system + judge prompt, so the rubric is part of the system.

## Governing principles

1. **Eval before feature.** No retrieval component is built before the harness
   that measures it. Phase 1 is the eval harness.
2. **Write-path intelligence, read-path speed.** Papers are written once,
   queried forever. Enrichment (claims, entities) happens at ingestion; the
   query path stays cheap. LLM grading at query time is an escape hatch for
   low-confidence retrievals, not a default step.
3. **Spend the novelty budget on the gaps.** Stack choices proven in the
   predecessor project (OpenSearch, Docling, Airflow, FastAPI) are kept.
   New effort goes into measurement, staged retrieval, and attribution.

## Retrieval quality requirements

- **Breadth over depth**: multiple retrievers with different failure modes
  (BM25 + dense over chunks, dense over claims, entity channel with
  IDF-style damping) fused — not one retriever tuned harder.
- **Semantic gate**: keyword/entity matches can reorder results but can never
  introduce a candidate with no semantic relationship to the query.
- **Rerank stage**: coarse retrieval over-fetches (≥4× top_k), a
  cross-encoder reranks before anything reaches generation.
- **Pre-filtering**: metadata constraints (category, date, author) are applied
  inside the retrieval query, never post-hoc.

## Non-goals

- Not a general web-search assistant — corpus is arXiv papers only.
- No conversational memory across sessions — out of scope.
- Streaming ingestion — arXiv publishes daily; a daily batch DAG plus
  on-demand ingestion by arXiv ID matches the domain's real freshness need.
- Multi-tenancy, auth, billing — single-user research tool.

## Interfaces (planned)

- REST API (FastAPI): ask, search, ingest-by-id, health.
- Simple chat UI (later phase; not a differentiator).

## Reference material

- Predecessor project: `~/Others/Agentic-RAG-project` (course-based; used as
  a pattern library and gap list, never copied from).
- Architecture and stage design: [architecture.md](architecture.md).
- Decisions and rejected alternatives: `doc/adr/`.
