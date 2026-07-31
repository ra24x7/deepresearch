from datetime import date

from ingestion.enrich.claims import ExtractedEntity
from ingestion.enrich.entities import entities_from_arxiv_ids, entities_from_authors, merge_entities
from ingestion.schemas import ArxivMetadata


def _metadata(authors: tuple[str, ...] = ("Jane Doe", "John Smith")) -> ArxivMetadata:
    return ArxivMetadata(
        arxiv_id="2501.00001",
        title="A Paper",
        authors=authors,
        abstract="An abstract.",
        categories=("cs.AI",),
        published=date(2025, 1, 1),
        pdf_url="https://arxiv.org/pdf/2501.00001",
    )


class TestEntitiesFromAuthors:
    def test_each_author_becomes_an_entity_with_author_type(self):
        entities = entities_from_authors(_metadata(("Jane Doe", "John Smith")))

        assert len(entities) == 2
        assert all(e.entity_type == "author" for e in entities)
        assert entities[0].surface_form == "Jane Doe"
        assert entities[0].entity_key == "jane doe"

    def test_no_authors_returns_empty_tuple(self):
        entities = entities_from_authors(_metadata(()))

        assert entities == ()


class TestEntitiesFromArxivIds:
    def test_finds_arxiv_id_in_section_text_and_tags_as_paper(self):
        sections = [("Related Work", "We build on prior work 2401.12345 for our baseline.")]

        entities = entities_from_arxiv_ids(sections)

        assert len(entities) == 1
        assert entities[0].surface_form == "2401.12345"
        assert entities[0].entity_type == "paper"
        assert entities[0].entity_key == "2401.12345"

    def test_finds_arxiv_id_with_version_suffix(self):
        sections = [("Related Work", "See arXiv:2401.12345v2 for details.")]

        entities = entities_from_arxiv_ids(sections)

        assert entities[0].surface_form == "2401.12345v2"

    def test_deduplicates_repeated_arxiv_ids_across_sections(self):
        sections = [
            ("Intro", "cites 2401.12345 here"),
            ("Related Work", "again cites 2401.12345 here"),
        ]

        entities = entities_from_arxiv_ids(sections)

        assert len(entities) == 1

    def test_no_arxiv_ids_returns_empty_tuple(self):
        entities = entities_from_arxiv_ids([("Intro", "no ids mentioned here")])

        assert entities == ()


class TestMergeEntities:
    def test_merges_authors_arxiv_ids_and_llm_entities(self):
        sections = [("Related Work", "builds on 2401.12345")]
        llm_entities = (ExtractedEntity(entity_key="bert", surface_form="BERT", entity_type="method"),)

        merged = merge_entities(llm_entities, _metadata(("Jane Doe",)), sections)

        keys = {e.entity_key for e in merged}
        assert keys == {"jane doe", "2401.12345", "bert"}

    def test_dedupes_across_sources_by_entity_key_keeping_first_surface_form(self):
        sections: list[tuple[str, str]] = []
        llm_entities = (ExtractedEntity(entity_key="jane doe", surface_form="jane doe", entity_type="author"),)

        merged = merge_entities(llm_entities, _metadata(("Jane Doe",)), sections)

        matches = [e for e in merged if e.entity_key == "jane doe"]
        assert len(matches) == 1
        assert matches[0].surface_form == "Jane Doe"

    def test_no_extras_and_no_llm_entities_returns_empty_tuple(self):
        merged = merge_entities((), _metadata(()), [])

        assert merged == ()
