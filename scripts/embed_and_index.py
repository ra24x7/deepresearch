"""Embed a corpus and load the three OpenSearch indices (LIVE Cohere calls).

Per paper: embed that paper's chunks, index them, move on. A failure costs one
paper, not the whole run — and --skip-existing resumes from where it stopped.

    uv run python scripts/embed_and_index.py --corpus evalv1 [--skip-existing] [--dry-run]
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
from db.models import Chunk, Claim, Entity, EntityLink, Paper
from db.session import get_engine, get_session_factory
from ingestion.embeddings.factory import build_provider
from search.filters import is_indexable_section
from search.indexer import create_indices, index_chunks, index_claims, index_entities
from search.indices import chunks_index_name

_REQUEST_TIMEOUT_SECONDS = 120


def build_clients(embedding: EmbeddingSettings):
    bedrock_client = None
    if embedding.provider != "fake":
        bedrock = BedrockSettings()
        bedrock_client = boto3.client(
            "bedrock-runtime",
            region_name=bedrock.region,
            config=Config(read_timeout=_REQUEST_TIMEOUT_SECONDS, connect_timeout=_REQUEST_TIMEOUT_SECONDS),
        )
    provider = build_provider(embedding, bedrock_client)
    host = OpenSearchSettings().host.replace("http://", "").replace("https://", "")
    hostname, _, port = host.partition(":")
    search_client = OpenSearch(hosts=[{"host": hostname, "port": int(port or 9200)}], timeout=_REQUEST_TIMEOUT_SECONDS)
    return provider, search_client


def already_indexed(client, corpus: str, arxiv_id: str) -> bool:
    body = {"query": {"term": {"arxiv_id": arxiv_id}}}
    return client.count(index=chunks_index_name(corpus), body=body)["count"] > 0


def main(corpus: str, skip_existing: bool, dry_run: bool, force: bool = False) -> int:
    load_dotenv()
    embedding = EmbeddingSettings()
    provider, client = build_clients(embedding)
    session_factory = get_session_factory(get_engine(PostgresSettings()))

    print(f"provider={provider.model_id} dim={provider.dimension} corpus={corpus}")
    if not dry_run:
        create_indices(client, corpus, provider.dimension, force=force)

    total_chunks = total_claims = total_failed = 0
    errors: list[str] = []

    def note_error(doc_id: str, exc: Exception) -> None:
        errors.append(f"{doc_id}: {exc}")
    with session_factory() as session:
        arxiv_ids = [row[0] for row in session.query(Paper.arxiv_id).filter_by(corpus=corpus).order_by(Paper.arxiv_id)]
        for i, arxiv_id in enumerate(arxiv_ids, 1):
            if skip_existing and not dry_run and already_indexed(client, corpus, arxiv_id):
                print(f"[{i}/{len(arxiv_ids)}] {arxiv_id}: already indexed, skipped", flush=True)
                continue

            chunks = [
                {
                    "chunk_id": c.chunk_id,
                    "arxiv_id": c.arxiv_id,
                    "section_title": c.section_title,
                    "part_index": c.part_index,
                    "word_count": c.word_count,
                    "text": c.text,
                }
                for c in session.query(Chunk).filter_by(arxiv_id=arxiv_id).all()
                if is_indexable_section(c.section_title)
            ]
            claims = [
                {
                    "claim_hash": cl.claim_hash,
                    "arxiv_id": cl.arxiv_id,
                    "section_title": cl.section_title,
                    "claim_text": cl.claim_text,
                }
                for cl in session.query(Claim).filter_by(arxiv_id=arxiv_id).all()
            ]
            if dry_run:
                print(f"[{i}/{len(arxiv_ids)}] {arxiv_id}: would embed {len(chunks)} chunks, {len(claims)} claims")
                total_chunks += len(chunks)
                total_claims += len(claims)
                continue

            indexed, failed = index_chunks(client, corpus, provider, chunks, on_error=note_error)
            total_chunks += indexed
            total_failed += failed
            if claims:
                c_indexed, c_failed = index_claims(client, corpus, provider, claims, on_error=note_error)
                total_claims += c_indexed
                total_failed += c_failed
            print(f"[{i}/{len(arxiv_ids)}] {arxiv_id}: {indexed} chunks, {len(claims)} claims indexed", flush=True)

        links_by_entity: dict[str, list[EntityLink]] = {}
        for link in session.query(EntityLink).all():
            links_by_entity.setdefault(link.entity_key, []).append(link)
        entities = [
            {
                "entity_key": e.entity_key,
                "surface_forms": e.surface_forms,
                "entity_type": e.entity_type,
                "link_count": e.link_count,
                "linked_arxiv_ids": sorted({link.arxiv_id for link in links_by_entity.get(e.entity_key, [])}),
                "linked_chunk_ids": sorted({link.chunk_id for link in links_by_entity.get(e.entity_key, [])}),
            }
            for e in session.query(Entity).all()
        ]

    if not dry_run and entities:
        e_indexed, e_failed = index_entities(client, corpus, entities, on_error=note_error)
        total_failed += e_failed
        print(f"entities indexed: {e_indexed}")

    print(f"\nchunks: {total_chunks}  claims: {total_claims}  entities: {len(entities)}  failed: {total_failed}")
    for line in errors[:5]:
        print(f"  error: {line}")
    return 1 if total_failed else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="delete and recreate indices first")
    args = ap.parse_args()
    sys.exit(main(args.corpus, args.skip_existing, args.dry_run, args.force))
