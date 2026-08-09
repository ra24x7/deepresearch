"""Solvability audit: every golden evidence quote must be findable in the parsed
paper text (Stage A) and wholly inside one indexed chunk (Stage B).

Runs locally against Postgres (POSTGRES__DSN). `formula` fields are linearized
transcriptions, never verbatim — they are not audited.
    uv run python scripts/solvability_audit.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import PostgresSettings
from db.models import Chunk, Paper
from db.session import get_engine, get_session_factory
from evals.solvability import audit_quote

GOLDEN_PATH = Path("data/golden_dataset.jsonl")
REPORT_PATH = Path("notebooks/phase2_ingestion/solvability_v1.json")


def load_answerable_entries() -> list[dict]:
    entries = [json.loads(line) for line in GOLDEN_PATH.read_text().splitlines() if line.strip()]
    return [e for e in entries if e.get("expected_behavior") == "answer"]


def truncated_quotes(records: list[dict], chunks_by_paper: dict) -> list[str]:
    """Quotes cut mid-word are verbatim and still wrong.

    A fixed-width mining window can end a span inside a word; the checker passes
    it (it is a real substring) while the reader loses the fact. In g051 the cut
    fell before 'an implementation edit', and the reference answer was written
    from the fragment.
    """
    offenders = []
    for record in records:
        quote = record.get("quote")
        if not quote:
            continue
        for _, text in chunks_by_paper.get(record["arxiv_id"], []):
            index = text.find(quote)
            if index < 0:
                continue
            after = text[index + len(quote) : index + len(quote) + 1]
            before = text[index - 1 : index] if index else " "
            if after.isalnum() or before.isalnum():
                offenders.append(record["question"])
            break
    return sorted(set(offenders))


def audit_all() -> dict:
    session_factory = get_session_factory(get_engine(PostgresSettings()))
    records = []
    with session_factory() as session:
        papers = {p.arxiv_id: p.raw_text for p in session.query(Paper).all()}
        chunks_by_paper: dict[str, list[tuple[str, str]]] = {}
        for chunk in session.query(Chunk).all():
            chunks_by_paper.setdefault(chunk.arxiv_id, []).append((chunk.chunk_id, chunk.text))

    for entry in load_answerable_entries():
        for evidence in entry.get("evidence", []):
            quote = evidence.get("quote")
            if not quote:
                continue
            arxiv_id = evidence["arxiv_id"]
            if arxiv_id not in papers:
                records.append({"question": entry["id"], "arxiv_id": arxiv_id, "status": "paper_missing"})
                continue
            result = audit_quote(quote, papers[arxiv_id], chunks_by_paper.get(arxiv_id, []))
            records.append(
                {
                    "question": entry["id"],
                    "arxiv_id": arxiv_id,
                    "where": evidence.get("where", ""),
                    "stage_a_found": result.stage_a.found,
                    "stage_a_match": result.stage_a.match,
                    "stage_b_found": result.stage_b_found,
                    "stage_b_match": result.stage_b_match,
                    "stage_b_chunk_id": result.stage_b_chunk_id,
                }
            )

    quote_records = [
        {"question": entry["id"], "arxiv_id": ev["arxiv_id"], "quote": ev.get("quote")}
        for entry in load_answerable_entries()
        for ev in entry.get("evidence", [])
    ]
    audited = [r for r in records if "stage_a_found" in r]
    fuzzy_only = sorted(
        {r["question"] for r in audited if r["stage_a_match"] == "fuzzy" or r["stage_b_match"] == "fuzzy"}
    )
    # An answer-expected entry with zero quotes passes vacuously; name it so
    # the pass is visibly hollow (g038 is metadata-computed by design).
    unauditable = sorted(
        e["id"] for e in load_answerable_entries() if not any(ev.get("quote") for ev in e.get("evidence", []))
    )
    return {
        "quotes": records,
        "summary": {
            "total_quotes": len(records),
            "unauditable_no_quotes": unauditable,
            "papers_missing": sum(1 for r in records if r.get("status") == "paper_missing"),
            "stage_a_passed": sum(1 for r in audited if r["stage_a_found"]),
            "stage_b_passed": sum(1 for r in audited if r["stage_b_found"]),
            "fuzzy_matches_need_review": fuzzy_only,
            "quotes_cut_mid_word": truncated_quotes(quote_records, chunks_by_paper),
        },
    }


def main() -> int:
    report = audit_all()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n")

    for r in report["quotes"]:
        if r.get("status") == "paper_missing":
            print(f"{r['question']}  {r['arxiv_id']}  PAPER MISSING")
            continue
        a = r["stage_a_match"] if r["stage_a_found"] else "FAIL"
        b = f"{r['stage_b_match']} -> {r['stage_b_chunk_id']}" if r["stage_b_found"] else "FAIL"
        print(f"{r['question']}  {r['arxiv_id']}  [{r['where']}]  A: {a}  B: {b}")

    s = report["summary"]
    print(f"\nquotes: {s['total_quotes']}  stage A: {s['stage_a_passed']}  stage B: {s['stage_b_passed']}")
    if s["unauditable_no_quotes"]:
        print(f"unauditable, no evidence quotes (by design): {', '.join(s['unauditable_no_quotes'])}")
    if s["fuzzy_matches_need_review"]:
        print(f"fuzzy (needs human review): {', '.join(s['fuzzy_matches_need_review'])}")
    if s["quotes_cut_mid_word"]:
        print(f"QUOTES CUT MID-WORD: {', '.join(s['quotes_cut_mid_word'])}")
    all_pass = (
        not s["quotes_cut_mid_word"]
        and s["papers_missing"] == 0
        and s["stage_a_passed"] == s["total_quotes"]
        and s["stage_b_passed"] == s["total_quotes"]
    )
    print("RESULT:", "PASS" if all_pass else "FAIL")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
