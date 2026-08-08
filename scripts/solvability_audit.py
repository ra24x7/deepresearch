"""Solvability audit: every golden evidence quote must be findable in the parsed
paper text (Stage A) and wholly inside one indexed chunk (Stage B).

Runs locally against Postgres (POSTGRES__DSN). `formula` fields are linearized
transcriptions, never verbatim — they are not audited.
    uv run python scripts/solvability_audit.py
"""

import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from clients import postgres_session_factory
from db.queries import chunks_by_paper as load_chunks_by_paper
from db.queries import raw_text_by_paper
from evals.report import write_json_report
from evals.solvability import audit_quote
from goldenset import load_answerable_entries

REPORT_PATH = Path("notebooks/phase2_ingestion/solvability_v1.json")


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
    session_factory = postgres_session_factory()
    records = []
    with session_factory() as session:
        papers = raw_text_by_paper(session)
        chunks_by_paper = load_chunks_by_paper(session)

    entries = load_answerable_entries()
    for entry in entries:
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
        for entry in entries
        for ev in entry.get("evidence", [])
    ]
    audited = [r for r in records if "stage_a_found" in r]
    fuzzy_only = sorted(
        {r["question"] for r in audited if r["stage_a_match"] == "fuzzy" or r["stage_b_match"] == "fuzzy"}
    )
    return {
        "quotes": records,
        "summary": {
            "total_quotes": len(records),
            "papers_missing": sum(1 for r in records if r.get("status") == "paper_missing"),
            "stage_a_passed": sum(1 for r in audited if r["stage_a_found"]),
            "stage_b_passed": sum(1 for r in audited if r["stage_b_found"]),
            "fuzzy_matches_need_review": fuzzy_only,
            "quotes_cut_mid_word": truncated_quotes(quote_records, chunks_by_paper),
        },
    }


def main() -> int:
    report = audit_all()
    write_json_report(REPORT_PATH, report)

    for r in report["quotes"]:
        if r.get("status") == "paper_missing":
            print(f"{r['question']}  {r['arxiv_id']}  PAPER MISSING")
            continue
        a = r["stage_a_match"] if r["stage_a_found"] else "FAIL"
        b = f"{r['stage_b_match']} -> {r['stage_b_chunk_id']}" if r["stage_b_found"] else "FAIL"
        print(f"{r['question']}  {r['arxiv_id']}  [{r['where']}]  A: {a}  B: {b}")

    s = report["summary"]
    print(f"\nquotes: {s['total_quotes']}  stage A: {s['stage_a_passed']}  stage B: {s['stage_b_passed']}")
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
