from datetime import date

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from db.models import Base, Chunk, EntityLink, Paper

EXPECTED_TABLES = {"papers", "chunks", "claims", "entities", "entity_links", "ingestion_runs"}


@pytest.fixture
def sqlite_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


class TestCreateAll:
    def test_create_all_succeeds_against_in_memory_sqlite(self, sqlite_engine):
        table_names = set(inspect(sqlite_engine).get_table_names())
        assert EXPECTED_TABLES.issubset(table_names)


class TestPaperRoundTrip:
    def test_paper_round_trip_insert_and_select(self, sqlite_engine):
        session = sessionmaker(bind=sqlite_engine)()
        paper = Paper(
            arxiv_id="2501.00001",
            title="A Paper",
            authors=["Jane Doe"],
            abstract="An abstract.",
            categories=["cs.AI"],
            published=date(2025, 1, 1),
            corpus="phase2-snapshot",
            raw_text="full text",
            sections=[{"title": "Intro", "text": "hello", "level": 1}],
            page_count=10,
        )
        session.add(paper)
        session.commit()

        fetched = session.get(Paper, "2501.00001")

        assert fetched.title == "A Paper"
        assert fetched.authors == ["Jane Doe"]
        assert fetched.corpus == "phase2-snapshot"
        session.close()


class TestForeignKeysAndCompositeKeys:
    def test_chunk_declares_foreign_key_to_paper(self):
        fk_columns = {fk.column.table.name for fk in Chunk.__table__.foreign_keys}
        assert "papers" in fk_columns

    def test_entity_link_has_composite_primary_key_of_three_columns(self):
        pk_columns = {c.name for c in EntityLink.__table__.primary_key.columns}
        assert pk_columns == {"entity_key", "arxiv_id", "chunk_id"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
