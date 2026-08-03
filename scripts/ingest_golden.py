"""Backfill golden papers: fetch metadata, parse local PDFs, chunk, persist.

Runs inside the Airflow container (Docling + POSTGRES__DSN available):
    python scripts/ingest_golden.py --corpus evalv1 2602.03442 ...
Idempotent: re-running replaces each paper's rows in one transaction.
"""

import argparse
import hashlib
import sys
from pathlib import Path

from config import ArxivSettings, ChunkingSettings, ParserSettings, PostgresSettings
from db.models import Chunk as ChunkRow
from db.models import EntityLink, Paper
from db.session import get_engine, get_session_factory
from ingestion.arxiv_client import download_pdf, fetch_by_ids
from ingestion.chunker import chunk_paper
from ingestion.parser import parse_pdf


def find_or_download_pdf(metadata, papers_dir: Path, settings: ArxivSettings) -> Path:
    matches = sorted(papers_dir.glob(f"{metadata.arxiv_id}.pdf")) + sorted(papers_dir.glob(f"{metadata.arxiv_id}v*.pdf"))
    if matches:
        return matches[-1]
    return download_pdf(metadata, papers_dir, settings)


def ingest(arxiv_ids: list[str], corpus: str, papers_dir: Path, skip_existing: bool = False) -> None:
    arxiv_settings = ArxivSettings()
    if skip_existing:
        session_factory = get_session_factory(get_engine(PostgresSettings()))
        with session_factory() as session:
            done = {row[0] for row in session.query(Paper.arxiv_id).all()}
        arxiv_ids = [aid for aid in arxiv_ids if aid not in done]
        if not arxiv_ids:
            print("nothing to ingest — all requested papers already present")
            return
    metadata_list = fetch_by_ids(arxiv_ids, arxiv_settings)
    parser_settings = ParserSettings()
    chunking_settings = ChunkingSettings()
    session_factory = get_session_factory(get_engine(PostgresSettings()))

    all_chunks = []
    with session_factory() as session:
        for metadata in metadata_list:
            content = parse_pdf(find_or_download_pdf(metadata, papers_dir, arxiv_settings), parser_settings)
            chunks = chunk_paper(metadata, content, chunking_settings)
            all_chunks.extend(chunks)

            # Re-ingest drops the paper's entity links (they reference chunk ids);
            # they are rebuilt by the enrichment pass, not here.
            session.query(EntityLink).filter_by(arxiv_id=metadata.arxiv_id).delete()
            session.query(ChunkRow).filter_by(arxiv_id=metadata.arxiv_id).delete()
            session.query(Paper).filter_by(arxiv_id=metadata.arxiv_id).delete()
            session.flush()
            session.add(
                Paper(
                    arxiv_id=metadata.arxiv_id,
                    title=metadata.title,
                    authors=list(metadata.authors),
                    abstract=metadata.abstract,
                    categories=list(metadata.categories),
                    published=metadata.published,
                    corpus=corpus,
                    raw_text=content.raw_text,
                    sections=[s.model_dump() for s in content.sections],
                    page_count=content.page_count,
                )
            )
            session.flush()
            session.add_all(
                ChunkRow(
                    chunk_id=c.chunk_id,
                    arxiv_id=c.arxiv_id,
                    section_title=c.section_title,
                    part_index=c.part_index,
                    word_count=c.word_count,
                    text=c.text,
                )
                for c in chunks
            )
            # Commit per paper: a long ingest that dies (docling is memory-hungry)
            # must not lose the papers it already parsed.
            session.commit()
            print(f"{metadata.arxiv_id}: {content.page_count} pages, {len(chunks)} chunks", flush=True)

    if not all_chunks:
        print("no chunks produced")
        return

    in_band = sum(1 for c in all_chunks if chunking_settings.min_words <= c.word_count <= chunking_settings.max_words)
    zero = sum(1 for c in all_chunks if c.word_count == 0)
    digest = hashlib.sha256("".join(c.text for c in sorted(all_chunks, key=lambda c: c.chunk_id)).encode()).hexdigest()
    print(f"total chunks: {len(all_chunks)}")
    print(f"in [{chunking_settings.min_words}, {chunking_settings.max_words}] words: {in_band} ({in_band / len(all_chunks):.1%})")
    print(f"zero-word chunks: {zero}")
    print(f"chunk-text sha256: {digest}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--papers-dir", default="data/papers")
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("arxiv_ids", nargs="+")
    args = ap.parse_args()
    try:
        ingest(args.arxiv_ids, args.corpus, Path(args.papers_dir), args.skip_existing)
    except Exception as exc:
        print(f"ingest failed: {exc}", file=sys.stderr)
        raise
