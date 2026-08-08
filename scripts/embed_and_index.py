"""Embed a corpus and load the three OpenSearch indices (LIVE Cohere calls).

Thin driver over src/pipeline — the same stage functions the Airflow DAG calls.
Per paper: embed that paper's chunks, index them, move on, so a failure costs
one paper. EMBEDDING__PROVIDER=fake runs the whole path without spending.

    uv run python scripts/embed_and_index.py --corpus evalv1 [--skip-existing] [--dry-run] [--force]
"""

import argparse
import sys

import _bootstrap  # noqa: F401
from dotenv import load_dotenv

from clients import embedding_provider, opensearch_client, postgres_session_factory
from db.models import Chunk
from db.queries import arxiv_ids_in_corpus
from pipeline.stages import default_pipeline_settings, embed_and_index_paper, index_entities_for_corpus
from search.filters import is_indexable_section
from search.indexer import create_indices
from search.indices import chunks_index_name


def already_indexed(client, corpus: str, arxiv_id: str) -> bool:
    return client.count(index=chunks_index_name(corpus), body={"query": {"term": {"arxiv_id": arxiv_id}}})["count"] > 0


def report_dry_run(session, corpus: str) -> int:
    arxiv_ids = arxiv_ids_in_corpus(session, corpus)
    indexable = 0
    for chunk in session.query(Chunk).all():
        if is_indexable_section(chunk.section_title):
            indexable += 1
    print(f"{len(arxiv_ids)} papers, {indexable} indexable chunks would be embedded")
    return 0


def main(corpus: str, skip_existing: bool, dry_run: bool, force: bool) -> int:
    load_dotenv()
    provider = embedding_provider()
    client = opensearch_client()
    settings = default_pipeline_settings()
    session_factory = postgres_session_factory()

    print(f"provider={provider.model_id} dim={provider.dimension} corpus={corpus}")
    with session_factory() as session:
        if dry_run:
            return report_dry_run(session, corpus)

        create_indices(client, corpus, provider.dimension, force=force)
        arxiv_ids = arxiv_ids_in_corpus(session, corpus)
        totals = {"chunks": 0, "claims": 0, "failed": 0}
        errors: list[str] = []

        for i, arxiv_id in enumerate(arxiv_ids, 1):
            if skip_existing and already_indexed(client, corpus, arxiv_id):
                print(f"[{i}/{len(arxiv_ids)}] {arxiv_id}: already indexed, skipped", flush=True)
                continue
            stats = embed_and_index_paper(arxiv_id, corpus, session, client, provider, settings)
            totals["chunks"] += stats["chunks_indexed"]
            totals["claims"] += stats["claims_indexed"]
            totals["failed"] += stats["failed"]
            errors.extend(stats["errors"])
            print(
                f"[{i}/{len(arxiv_ids)}] {arxiv_id}: {stats['chunks_indexed']} chunks, "
                f"{stats['claims_indexed']} claims indexed",
                flush=True,
            )

        entity_stats = index_entities_for_corpus(corpus, session, client)

    print(
        f"\nchunks: {totals['chunks']}  claims: {totals['claims']}  "
        f"entities: {entity_stats['entities_indexed']}  failed: {totals['failed'] + entity_stats['failed']}"
    )
    for line in errors[:5]:
        print(f"  error: {line}")
    return 1 if totals["failed"] or entity_stats["failed"] else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="delete and recreate indices first")
    args = ap.parse_args()
    sys.exit(main(args.corpus, args.skip_existing, args.dry_run, args.force))
