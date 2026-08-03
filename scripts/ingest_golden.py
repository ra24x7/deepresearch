"""Backfill papers into Postgres: fetch, parse, chunk. No LLM, no embeddings.

Thin driver over src/pipeline — the same stage function the Airflow DAG calls.

    uv run python scripts/ingest_golden.py --corpus evalv1 [--skip-existing] 2602.03442 ...
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import PostgresSettings
from db.models import Paper
from db.session import get_engine, get_session_factory
from pipeline.stages import default_pipeline_settings, parse_and_chunk_paper


def main(arxiv_ids: list[str], corpus: str, papers_dir: Path, skip_existing: bool) -> int:
    settings = default_pipeline_settings()
    session_factory = get_session_factory(get_engine(PostgresSettings()))
    totals = {"papers": 0, "chunks": 0, "words": 0}
    failures: list[str] = []

    with session_factory() as session:
        if skip_existing:
            done = {row[0] for row in session.query(Paper.arxiv_id).all()}
            arxiv_ids = [aid for aid in arxiv_ids if aid not in done]
            if not arxiv_ids:
                print("nothing to ingest — all requested papers already present")
                return 0

        for i, arxiv_id in enumerate(arxiv_ids, 1):
            try:
                stats = parse_and_chunk_paper(arxiv_id, corpus, papers_dir, session, settings)
            except Exception as exc:  # noqa: BLE001 — one bad paper must not end a 500-paper run
                failures.append(f"{arxiv_id}: {exc}")
                print(f"[{i}/{len(arxiv_ids)}] {arxiv_id}: FAILED — {exc}", flush=True)
                continue
            totals["papers"] += 1
            totals["chunks"] += stats["chunks"]
            totals["words"] += stats["words"]
            print(f"[{i}/{len(arxiv_ids)}] {arxiv_id}: {stats['pages']} pages, {stats['chunks']} chunks", flush=True)

    print(f"\npapers: {totals['papers']}  chunks: {totals['chunks']}  words: {totals['words']:,}")
    for line in failures:
        print(f"  failed: {line}")
    return 1 if failures else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--papers-dir", default="data/papers")
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("arxiv_ids", nargs="+")
    args = ap.parse_args()
    sys.exit(main(args.arxiv_ids, args.corpus, Path(args.papers_dir), args.skip_existing))
