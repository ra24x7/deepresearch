"""Embed a corpus and load the three OpenSearch indices (LIVE Cohere calls).

Thin driver over src/pipeline — the same stage functions the Airflow DAG calls.
Per paper: embed that paper's chunks, index them, move on, so a failure costs
one paper. EMBEDDING__PROVIDER=fake runs the whole path without spending.

    uv run python scripts/embed_and_index.py --corpus evalv1 [--skip-existing] [--dry-run] [--force]
"""

import argparse
import sys
from pathlib import Path

import boto3
from botocore.config import Config
from dotenv import load_dotenv
from opensearchpy import OpenSearch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import BedrockSettings, EmbeddingSettings, OpenSearchSettings, PostgresSettings
from db.models import Chunk, Paper
from db.session import get_engine, get_session_factory
from ingestion.embeddings.factory import build_provider
from pipeline.stages import default_pipeline_settings, embed_and_index_paper, index_entities_for_corpus
from search.filters import is_indexable_section
from search.indexer import create_indices
from search.indices import chunks_index_name

_REQUEST_TIMEOUT_SECONDS = 120
_MAX_PRINTED_ERRORS = 5


def build_clients(embedding: EmbeddingSettings):
    bedrock_client = None
    if embedding.provider != "fake":
        bedrock_client = boto3.client(
            "bedrock-runtime",
            region_name=BedrockSettings().region,
            config=Config(read_timeout=_REQUEST_TIMEOUT_SECONDS, connect_timeout=_REQUEST_TIMEOUT_SECONDS),
        )
    provider = build_provider(embedding, bedrock_client)
    host = OpenSearchSettings().host.replace("http://", "").replace("https://", "")
    hostname, _, port = host.partition(":")
    search = OpenSearch(hosts=[{"host": hostname, "port": int(port or 9200)}], timeout=_REQUEST_TIMEOUT_SECONDS)
    return provider, search


def already_indexed(client, corpus: str, arxiv_id: str) -> bool:
    return client.count(index=chunks_index_name(corpus), body={"query": {"term": {"arxiv_id": arxiv_id}}})["count"] > 0


def report_dry_run(session, corpus: str) -> int:
    arxiv_ids = [row[0] for row in session.query(Paper.arxiv_id).filter_by(corpus=corpus).order_by(Paper.arxiv_id)]
    indexable = 0
    for chunk in session.query(Chunk).all():
        if is_indexable_section(chunk.section_title):
            indexable += 1
    print(f"{len(arxiv_ids)} papers, {indexable} indexable chunks would be embedded")
    return 0


def main(corpus: str, skip_existing: bool, dry_run: bool, force: bool) -> int:
    load_dotenv()
    embedding = EmbeddingSettings()
    provider, client = build_clients(embedding)
    settings = default_pipeline_settings()
    session_factory = get_session_factory(get_engine(PostgresSettings()))

    print(f"provider={provider.model_id} dim={provider.dimension} corpus={corpus}")
    with session_factory() as session:
        if dry_run:
            return report_dry_run(session, corpus)

        create_indices(client, corpus, provider.dimension, force=force)
        arxiv_ids = [row[0] for row in session.query(Paper.arxiv_id).filter_by(corpus=corpus).order_by(Paper.arxiv_id)]
        totals = {"chunks": 0, "claims": 0, "failed": 0}
        errors: list[str] = []

        for i, arxiv_id in enumerate(arxiv_ids, 1):
            if skip_existing and already_indexed(client, corpus, arxiv_id):
                print(f"[{i}/{len(arxiv_ids)}] {arxiv_id}: already indexed, skipped", flush=True)
                continue
            try:
                stats = embed_and_index_paper(arxiv_id, corpus, session, client, provider, settings)
            except Exception as exc:  # noqa: BLE001 — one paper must not abort a paid batch
                session.rollback()
                totals["failed"] += 1
                errors.append(f"{arxiv_id}: {exc}")
                print(f"[{i}/{len(arxiv_ids)}] {arxiv_id}: FAILED — {exc}", flush=True)
                continue
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
    for line in errors[:_MAX_PRINTED_ERRORS]:
        print(f"  error: {line}")
    if len(errors) > _MAX_PRINTED_ERRORS:
        print(f"  ... and {len(errors) - _MAX_PRINTED_ERRORS} more errors")
    return 1 if totals["failed"] or entity_stats["failed"] else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="delete and recreate indices first")
    args = ap.parse_args()
    sys.exit(main(args.corpus, args.skip_existing, args.dry_run, args.force))
