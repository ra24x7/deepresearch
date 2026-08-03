"""Gate A: LLM claim+entity enrichment of the golden papers (LIVE Bedrock calls).

One Haiku call per paper (plus at most one JSON-repair retry each). Persists
claims/entities/entity_links, prints the cost ledger, and writes a 20-claim
spot-check sheet for the user to grade.

    uv run python scripts/enrich_golden.py 2602.03442 2606.21649 2606.23997 2607.24663
"""

import random
import sys
from functools import partial
from pathlib import Path

import boto3
from botocore.config import Config
from dotenv import load_dotenv
from sqlalchemy import func

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import BedrockSettings, EnrichmentSettings, PostgresSettings
from db.models import Chunk as ChunkRow
from db.models import Claim, Entity, EntityLink, Paper
from db.session import get_engine, get_session_factory
from ingestion.enrich.claims import extract_claims_and_entities
from ingestion.enrich.entities import merge_entities
from ingestion.schemas import ArxivMetadata
from llm.bedrock import invoke_json
from llm.cost import CostLedger
from textnorm import normalize

SPOTCHECK_PATH = Path("notebooks/phase2_ingestion/claim_spotcheck.md")
SPOTCHECK_SAMPLE = 20


def metadata_from_row(paper: Paper) -> ArxivMetadata:
    return ArxivMetadata(
        arxiv_id=paper.arxiv_id,
        title=paper.title,
        authors=tuple(paper.authors),
        abstract=paper.abstract,
        categories=tuple(paper.categories),
        published=paper.published,
        pdf_url="",
    )


def persist(session, result, metadata, sections, chunks) -> tuple[int, int, int]:
    new_claims = 0
    for claim in result.claims:
        if session.get(Claim, claim.claim_hash) is None:
            session.add(
                Claim(
                    claim_hash=claim.claim_hash,
                    arxiv_id=claim.arxiv_id,
                    claim_text=claim.claim_text,
                    section_title=claim.section_title,
                )
            )
            new_claims += 1

    all_entities = merge_entities(result.entities, metadata, sections)
    normalized_chunks = {chunk.chunk_id: normalize(chunk.text) for chunk in chunks}
    new_links = 0
    for entity in all_entities:
        if session.get(Entity, entity.entity_key) is None:
            session.add(
                Entity(
                    entity_key=entity.entity_key,
                    surface_forms=[entity.surface_form],
                    entity_type=entity.entity_type,
                )
            )
            session.flush()
        for chunk in chunks:
            link_key = (entity.entity_key, chunk.arxiv_id, chunk.chunk_id)
            if entity.entity_key in normalized_chunks[chunk.chunk_id] and session.get(EntityLink, link_key) is None:
                session.add(EntityLink(entity_key=entity.entity_key, arxiv_id=chunk.arxiv_id, chunk_id=chunk.chunk_id))
                new_links += 1
    return new_claims, len(all_entities), new_links


def refresh_link_counts(session) -> None:
    counts = dict(
        session.query(EntityLink.entity_key, func.count(func.distinct(EntityLink.arxiv_id)))
        .group_by(EntityLink.entity_key)
        .all()
    )
    for entity in session.query(Entity).all():
        entity.link_count = counts.get(entity.entity_key, 0)


def write_spotcheck(session) -> int:
    claims = session.query(Claim).order_by(Claim.claim_hash).all()
    sample = random.Random(42).sample(claims, min(SPOTCHECK_SAMPLE, len(claims)))
    lines = [
        "# Claim spot-check (Gate A)",
        "",
        "Grade each claim: is it a faithful, atomic statement supported by the paper?",
        "Mark [s] supported / [u] unsupported / [v] vague. Only the user's grades count.",
        "",
    ]
    for i, claim in enumerate(sample, 1):
        lines.append(f"{i}. [ ] ({claim.arxiv_id}, {claim.section_title})")
        lines.append(f"   {claim.claim_text}")
        lines.append("")
    SPOTCHECK_PATH.write_text("\n".join(lines))
    return len(sample)


def main(arxiv_ids: list[str]) -> int:
    load_dotenv()
    bedrock = BedrockSettings()
    enrichment = EnrichmentSettings()
    client = boto3.client(
        "bedrock-runtime",
        region_name=bedrock.region,
        config=Config(read_timeout=enrichment.timeout_seconds, connect_timeout=enrichment.timeout_seconds),
    )
    llm = partial(invoke_json, client=client, settings=enrichment)

    session_factory = get_session_factory(get_engine(PostgresSettings()))
    ledger = CostLedger()

    with session_factory() as session:
        for arxiv_id in arxiv_ids:
            paper = session.get(Paper, arxiv_id)
            if paper is None:
                print(f"{arxiv_id}: NOT IN papers TABLE — skipped")
                continue
            sections = [(s["title"], s["text"]) for s in paper.sections]
            metadata = metadata_from_row(paper)

            result = extract_claims_and_entities(metadata, sections, lambda p: llm(p), enrichment)
            ledger = ledger.add(result.usage)

            chunks = session.query(ChunkRow).filter_by(arxiv_id=arxiv_id).all()
            n_claims, n_entities, n_links = persist(session, result, metadata, sections, chunks)

            warn = f"  WARNING: {result.warning}" if result.warning else ""
            print(f"{arxiv_id}: {len(result.claims)} claims ({n_claims} new), "
                  f"{n_entities} entities, {n_links} chunk links{warn}")

        refresh_link_counts(session)
        n_sampled = write_spotcheck(session)
        session.commit()

    print(f"\ntokens: {ledger.input_tokens} in / {ledger.output_tokens} out")
    print(f"total cost: ${ledger.total_usd:.4f}  per paper: ${ledger.per_paper_usd(len(arxiv_ids)):.4f}")
    print(f"spot-check sheet ({n_sampled} claims): {SPOTCHECK_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
