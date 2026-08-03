# ADR 0003 — Bibliographies are entities, not retrievable text

Date: 2026-08-03
Status: accepted
Evidence: `notebooks/phase2_ingestion/solvability_v1.json` (0 of 31 golden
evidence quotes resolve to a reference chunk); corpus measurement over 1,624
chunks

## Decision

Chunks whose section title is *entirely* bibliographic (`References`,
`REFERENCES`, `VIII. REFERENCES`, `Bibliography`) are excluded from the
searchable chunk index. They remain in Postgres.

Matching is component-wise over merged titles and word-bounded
(`src/search/filters.py`). Acknowledgments stay indexed.

## Why

- Reference prose is bibliographic apparatus: it matches many queries by
  surface tokens while answering none. 106 of 1,624 chunks (6.5%, 55.7k words).
- The citation signal is captured as *structure* instead: the arXiv-id miner
  in `src/ingestion/enrich/entities.py` reads that same text from Postgres and
  produces typed `paper` entities with link counts — which is how
  "what cites X?" should be answered, not by keyword-matching reference lists.
- Two consumers want different things from the same text, so the filter belongs
  at the index boundary, not the chunk boundary. Filtering earlier would starve
  the entity miner.

## Trade-offs accepted

- A question needing a full citation string ("what is reference [12]?") would
  regress. None exists in the golden dataset, and the entity channel serves
  citation lookups better.
- Component-wise matching deliberately **keeps** merged chunks like
  `Conclusion + References` and `CCS Concepts + ... + 1 Introduction`, so some
  reference text survives inside chunks carrying real content. Conservative on
  purpose: a naive substring rule would have deleted introductions and
  conclusions.
- Acknowledgments are kept on judgement, not evidence: they hold funding and
  affiliation facts a future golden question could plausibly ask about.
