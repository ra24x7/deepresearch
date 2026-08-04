from sqlalchemy import JSON, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Paper(Base):
    __tablename__ = "papers"

    arxiv_id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    authors = Column(JSON, nullable=False)
    abstract = Column(Text, nullable=False)
    categories = Column(JSON, nullable=False)
    published = Column(Date, nullable=False)
    corpus = Column(Text, nullable=False)
    raw_text = Column(Text, nullable=False)
    sections = Column(JSON, nullable=False)
    page_count = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class Chunk(Base):
    __tablename__ = "chunks"

    chunk_id = Column(String, primary_key=True)
    arxiv_id = Column(String, ForeignKey("papers.arxiv_id"), nullable=False)
    section_title = Column(String, nullable=False)
    part_index = Column(Integer, nullable=False)
    word_count = Column(Integer, nullable=False)
    page_start = Column(Integer, nullable=True)
    page_end = Column(Integer, nullable=True)
    text = Column(Text, nullable=False)


class Claim(Base):
    __tablename__ = "claims"

    claim_hash = Column(String, primary_key=True)
    arxiv_id = Column(String, ForeignKey("papers.arxiv_id"), nullable=False)
    claim_text = Column(Text, nullable=False)
    section_title = Column(String, nullable=False)


class Entity(Base):
    __tablename__ = "entities"

    entity_key = Column(String, primary_key=True)
    surface_forms = Column(JSON, nullable=False)
    entity_type = Column(String, nullable=False)
    link_count = Column(Integer, nullable=False, server_default="0")


class EntityLink(Base):
    __tablename__ = "entity_links"

    entity_key = Column(String, ForeignKey("entities.entity_key"), primary_key=True)
    arxiv_id = Column(String, ForeignKey("papers.arxiv_id"), primary_key=True)
    chunk_id = Column(String, ForeignKey("chunks.chunk_id"), primary_key=True)


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    run_id = Column(String, primary_key=True)
    corpus = Column(Text, nullable=False)
    papers_processed = Column(Integer, nullable=False)
    chunks_indexed = Column(Integer, nullable=False)
    claims_indexed = Column(Integer, nullable=False)
    entities_upserted = Column(Integer, nullable=False)
    llm_input_tokens = Column(Integer, nullable=False)
    llm_output_tokens = Column(Integer, nullable=False)
    total_cost_usd = Column(Float, nullable=False)
    cost_per_paper_usd = Column(Float, nullable=False)
    duration_s = Column(Float, nullable=False)
    failures = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
