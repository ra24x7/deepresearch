"""Per-paper orchestration extracted from scripts/{ingest,enrich,embed_and_index}_golden.py.

Each function does one paper's worth of work against an injected DB session /
LLM callable / search client, so Airflow tasks can be thin wrappers over them.
No live API calls happen here — callers inject already-configured clients.
"""

from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from sqlalchemy import func

from config import ArxivSettings, ChunkingSettings, EnrichmentSettings, ParserSettings
from db.models import Chunk as ChunkRow
from db.models import Claim, Entity, EntityLink, Paper
from ingestion.arxiv_client import download_pdf, fetch_by_ids
from ingestion.chunker import chunk_paper
from ingestion.enrich.claims import ExtractedEntity, extract_claims_and_entities
from ingestion.enrich.entities import merge_entities
from ingestion.parser import parse_pdf
from ingestion.schemas import ArxivMetadata
from search.filters import is_indexable_section
from search.indexer import index_chunks, index_claims, index_entities
from textnorm import normalize


class PipelineSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    arxiv: ArxivSettings
    parser: ParserSettings
    chunking: ChunkingSettings
    enrichment: EnrichmentSettings


def default_pipeline_settings() -> PipelineSettings:
    return PipelineSettings(
        arxiv=ArxivSettings(),
        parser=ParserSettings(),
        chunking=ChunkingSettings(),
        enrichment=EnrichmentSettings(),
    )


def parse_and_chunk_paper(arxiv_id: str, corpus: str, papers_dir: Path, session, settings: PipelineSettings) -> dict:
    metadata = fetch_by_ids([arxiv_id], settings.arxiv)[0]
    pdf_path = _find_or_download_pdf(metadata, papers_dir, settings.arxiv)
    content = parse_pdf(pdf_path, settings.parser)
    chunks = chunk_paper(metadata, content, settings.chunking)

    # Re-ingest drops the paper's entity links (they reference chunk ids);
    # they are rebuilt by the enrichment pass, not here. The Paper row is
    # updated rather than replaced: claims reference it, and deleting it would
    # discard LLM output that cost money to produce.
    session.query(EntityLink).filter_by(arxiv_id=arxiv_id).delete()
    session.query(ChunkRow).filter_by(arxiv_id=arxiv_id).delete()
    session.flush()
    session.merge(
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
            page_start=c.page_start,
            page_end=c.page_end,
            text=c.text,
        )
        for c in chunks
    )
    session.commit()

    return {
        "arxiv_id": arxiv_id,
        "pages": content.page_count,
        "chunks": len(chunks),
        "words": sum(c.word_count for c in chunks),
    }


def _find_or_download_pdf(metadata: ArxivMetadata, papers_dir: Path, settings: ArxivSettings) -> Path:
    matches = sorted(papers_dir.glob(f"{metadata.arxiv_id}.pdf")) + sorted(papers_dir.glob(f"{metadata.arxiv_id}v*.pdf"))
    if matches:
        return matches[-1]
    return download_pdf(metadata, papers_dir, settings)


def enrich_paper(arxiv_id: str, session, llm_invoke_json: Callable, settings: PipelineSettings) -> dict:
    paper = session.get(Paper, arxiv_id)
    if paper is None:
        raise ValueError(f"paper not found in database: {arxiv_id}")

    sections = [(s["title"], s["text"]) for s in paper.sections]
    metadata = _metadata_from_row(paper)

    result = extract_claims_and_entities(metadata, sections, llm_invoke_json, settings.enrichment)
    chunks = session.query(ChunkRow).filter_by(arxiv_id=arxiv_id).all()

    new_claims = _persist_claims(session, result.claims)
    all_entities = merge_entities(result.entities, metadata, sections)
    new_links = _persist_entities_and_links(session, all_entities, chunks)
    _refresh_link_counts(session, [entity.entity_key for entity in all_entities])
    session.commit()

    return {
        "arxiv_id": arxiv_id,
        "claims": new_claims,
        "entities": len(all_entities),
        "links": new_links,
        "input_tokens": result.usage.input_tokens,
        "output_tokens": result.usage.output_tokens,
        "warning": result.warning,
    }


def _metadata_from_row(paper: Paper) -> ArxivMetadata:
    return ArxivMetadata(
        arxiv_id=paper.arxiv_id,
        title=paper.title,
        authors=tuple(paper.authors),
        abstract=paper.abstract,
        categories=tuple(paper.categories),
        published=paper.published,
        pdf_url="",
    )


def _persist_claims(session, claims) -> int:
    new_claims = 0
    for claim in claims:
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
    return new_claims


def _persist_entities_and_links(session, entities: tuple[ExtractedEntity, ...], chunks: list[ChunkRow]) -> int:
    normalized_chunks = {chunk.chunk_id: normalize(chunk.text) for chunk in chunks}
    new_links = 0
    for entity in entities:
        if session.get(Entity, entity.entity_key) is None:
            session.add(
                Entity(entity_key=entity.entity_key, surface_forms=[entity.surface_form], entity_type=entity.entity_type)
            )
            session.flush()
        for chunk in chunks:
            link_key = (entity.entity_key, chunk.arxiv_id, chunk.chunk_id)
            if entity.entity_key in normalized_chunks[chunk.chunk_id] and session.get(EntityLink, link_key) is None:
                session.add(EntityLink(entity_key=entity.entity_key, arxiv_id=chunk.arxiv_id, chunk_id=chunk.chunk_id))
                new_links += 1
    return new_links


def _refresh_link_counts(session, entity_keys: list[str]) -> None:
    if not entity_keys:
        return
    counts = dict(
        session.query(EntityLink.entity_key, func.count(func.distinct(EntityLink.arxiv_id)))
        .filter(EntityLink.entity_key.in_(entity_keys))
        .group_by(EntityLink.entity_key)
        .all()
    )
    for entity in session.query(Entity).filter(Entity.entity_key.in_(entity_keys)).all():
        entity.link_count = counts.get(entity.entity_key, 0)


def embed_and_index_paper(
    arxiv_id: str, corpus: str, session, search_client, provider, settings: PipelineSettings
) -> dict:
    chunks = [
        {
            "chunk_id": c.chunk_id,
            "arxiv_id": c.arxiv_id,
            "section_title": c.section_title,
            "part_index": c.part_index,
            "word_count": c.word_count,
            "text": c.text,
        }
        for c in session.query(ChunkRow).filter_by(arxiv_id=arxiv_id).all()
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

    errors: list[str] = []

    def note_error(doc_id: str, exc: Exception) -> None:
        errors.append(f"{doc_id}: {exc}")

    chunks_indexed, chunks_failed = index_chunks(search_client, corpus, provider, chunks, on_error=note_error)
    claims_indexed = claims_failed = 0
    if claims:
        claims_indexed, claims_failed = index_claims(search_client, corpus, provider, claims, on_error=note_error)

    return {
        "arxiv_id": arxiv_id,
        "chunks_indexed": chunks_indexed,
        "claims_indexed": claims_indexed,
        "failed": chunks_failed + claims_failed,
        "errors": errors,
    }


def index_entities_for_corpus(corpus: str, session, search_client) -> dict:
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

    indexed, failed = index_entities(search_client, corpus, entities)
    return {"entities_indexed": indexed, "failed": failed}
