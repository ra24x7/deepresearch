# Phase 2 — Enriched Ingestion (in progress)

## Solvability audit v1 (2026-07-30)

Every golden evidence quote must survive parsing (Stage A: found in the paper's
parsed text) and chunking (Stage B: wholly inside one chunk). `formula` fields
are linearized transcriptions and are not audited.

**Result: 31/31 quotes pass both stages** over the 4 golden papers
(150 chunks, 100% inside the 100–800-word band). Full per-quote detail in
`solvability_v1.json`.

What it took to get there — three parser/matching defects the audit surfaced:

1. **Math/code tokenization.** Docling inserts spaces around math and code
   tokens ("47 . 4", "edge _ search"). Fixed in matching: a
   whitespace-stripped exact tier plus Unicode minus/hyphen mapping in
   `normalize()`.
2. **Caption interleaving.** Docling places figure captions in layout order,
   which split a quoted sentence mid-way ("stem from reasoning ⟨Figure 5
   caption⟩ chain errors", g023). Fixed in the parser: caption-labeled
   elements defer to the end of their section, and `raw_text` is built from
   the section view so parse- and chunk-level text agree.
3. Without those, 3/31 quotes failed outright and 12 matched only fuzzily.

## Caveats

- **6 fuzzy-only matches await human review** (g003, g007, g013, g014, g016,
  g024): found at ≥95 partial-ratio but not verbatim after normalization.
  Only the user signs these off.
- The audit covers the 4 golden papers. The frozen snapshot
  (`data/eval_snapshot.json`, `evalv1`, 4 golden + 50 distractors pinned
  2026-07-30) is defined but distractors are not yet ingested — that happens
  with Phase 2.5 indexing, after which the audit re-runs (Stage C, against
  the live index) in Phase 2.6.
- Stage A/B run against Postgres content, not OpenSearch — index-level
  findability (Stage C) is deliberately deferred until indices exist.
