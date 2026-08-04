from datetime import date
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import ArxivSettings, ChunkingSettings, EnrichmentSettings, ParserSettings
from db.models import Base, Claim, Entity, EntityLink, Paper
from db.models import Chunk as ChunkRow
from ingestion.embeddings.fake import FakeEmbeddingProvider
from ingestion.schemas import ArxivMetadata, PaperSection, PdfContent
from llm.bedrock import Usage
from pipeline.stages import (
    PipelineSettings,
    default_pipeline_settings,
    embed_and_index_paper,
    enrich_paper,
    index_entities_for_corpus,
    parse_and_chunk_paper,
)

CLAIMS_5 = [{"text": f"Claim number {i}", "section_title": "Introduction"} for i in range(5)]
BERT_ENTITY = [{"surface_form": "BERT", "entity_type": "method"}]


def _words(n: int, prefix: str = "word") -> str:
    return " ".join(f"{prefix}{i}" for i in range(n))


def _metadata(arxiv_id: str = "2501.00001") -> ArxivMetadata:
    return ArxivMetadata(
        arxiv_id=arxiv_id,
        title="A Great Paper",
        authors=("Jane Doe",),
        abstract="An abstract.",
        categories=("cs.AI",),
        published=date(2025, 1, 1),
        pdf_url="https://arxiv.org/pdf/2501.00001v1",
    )


def _pdf_content() -> PdfContent:
    sections = (
        PaperSection(title="Introduction", text=_words(150), level=1),
        PaperSection(title="Method", text=_words(150, prefix="m"), level=1),
    )
    return PdfContent(raw_text="full text", sections=sections, page_count=7)


_DEFAULT_USAGE = Usage(input_tokens=10, output_tokens=5)


def _stub_llm(data: dict, usage: Usage = _DEFAULT_USAGE):
    def _invoke(prompt: str) -> tuple[dict, Usage]:
        return data, usage

    return _invoke


def _insert_paper(session, arxiv_id: str = "2501.00001", sections: list[dict] | None = None) -> Paper:
    sections = sections or [{"title": "Introduction", "text": "BERT improves accuracy on tasks.", "level": 1}]
    paper = Paper(
        arxiv_id=arxiv_id,
        title="A Great Paper",
        authors=["Jane Doe"],
        abstract="An abstract.",
        categories=["cs.AI"],
        published=date(2025, 1, 1),
        corpus="evalv1",
        raw_text="full text",
        sections=sections,
        page_count=5,
    )
    session.add(paper)
    session.flush()
    return paper


def _insert_chunk(session, arxiv_id: str, chunk_id: str, text: str, section_title: str = "Introduction") -> ChunkRow:
    chunk = ChunkRow(
        chunk_id=chunk_id, arxiv_id=arxiv_id, section_title=section_title, part_index=0, word_count=len(text.split()), text=text
    )
    session.add(chunk)
    session.flush()
    return chunk


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as s:
        yield s
    engine.dispose()


@pytest.fixture
def settings() -> PipelineSettings:
    return PipelineSettings(
        arxiv=ArxivSettings(),
        parser=ParserSettings(),
        chunking=ChunkingSettings(),
        enrichment=EnrichmentSettings(prompt_max_chars=2000),
    )


class TestDefaultPipelineSettings:
    def test_builds_settings_bundle_from_env_backed_classes(self):
        result = default_pipeline_settings()

        assert isinstance(result, PipelineSettings)
        assert isinstance(result.arxiv, ArxivSettings)
        assert isinstance(result.parser, ParserSettings)
        assert isinstance(result.chunking, ChunkingSettings)
        assert isinstance(result.enrichment, EnrichmentSettings)

    def test_pipeline_settings_is_frozen(self):
        settings = default_pipeline_settings()

        with pytest.raises(ValidationError):
            settings.arxiv = ArxivSettings()


class TestParseAndChunkPaper:
    def test_persists_paper_and_chunks(self, mocker, session, settings, tmp_path):
        (tmp_path / "2501.00001.pdf").write_bytes(b"%PDF-1.4")
        mocker.patch("pipeline.stages.fetch_by_ids", return_value=[_metadata()])
        mocker.patch("pipeline.stages.parse_pdf", return_value=_pdf_content())

        result = parse_and_chunk_paper("2501.00001", "evalv1", tmp_path, session, settings)

        assert result == {"arxiv_id": "2501.00001", "pages": 7, "chunks": 2, "words": 300}
        paper = session.get(Paper, "2501.00001")
        assert paper.corpus == "evalv1"
        assert paper.title == "A Great Paper"
        assert paper.page_count == 7
        assert session.query(ChunkRow).filter_by(arxiv_id="2501.00001").count() == 2

    def test_downloads_pdf_when_not_found_locally(self, mocker, session, settings, tmp_path):
        mocker.patch("pipeline.stages.fetch_by_ids", return_value=[_metadata()])
        mocker.patch("pipeline.stages.parse_pdf", return_value=_pdf_content())
        download_mock = mocker.patch("pipeline.stages.download_pdf", return_value=tmp_path / "2501.00001.pdf")

        parse_and_chunk_paper("2501.00001", "evalv1", tmp_path, session, settings)

        download_mock.assert_called_once()

    def test_finds_versioned_pdf_without_downloading(self, mocker, session, settings, tmp_path):
        (tmp_path / "2501.00001v2.pdf").write_bytes(b"%PDF-1.4")
        mocker.patch("pipeline.stages.fetch_by_ids", return_value=[_metadata()])
        mocker.patch("pipeline.stages.parse_pdf", return_value=_pdf_content())
        download_mock = mocker.patch("pipeline.stages.download_pdf")

        parse_and_chunk_paper("2501.00001", "evalv1", tmp_path, session, settings)

        download_mock.assert_not_called()

    def test_rerun_is_idempotent_row_counts_unchanged(self, mocker, session, settings, tmp_path):
        (tmp_path / "2501.00001.pdf").write_bytes(b"%PDF-1.4")
        mocker.patch("pipeline.stages.fetch_by_ids", return_value=[_metadata()])
        mocker.patch("pipeline.stages.parse_pdf", return_value=_pdf_content())

        parse_and_chunk_paper("2501.00001", "evalv1", tmp_path, session, settings)
        result_2 = parse_and_chunk_paper("2501.00001", "evalv1", tmp_path, session, settings)

        assert result_2 == {"arxiv_id": "2501.00001", "pages": 7, "chunks": 2, "words": 300}
        assert session.query(Paper).count() == 1
        assert session.query(ChunkRow).filter_by(arxiv_id="2501.00001").count() == 2


class TestEnrichPaper:
    def test_persists_claims_entities_and_links(self, session, settings):
        _insert_paper(session)
        _insert_chunk(session, "2501.00001", "2501.00001::intro::0", "BERT improves accuracy on tasks.")
        llm = _stub_llm({"claims": CLAIMS_5, "entities": BERT_ENTITY})

        result = enrich_paper("2501.00001", session, llm, settings)

        assert result["arxiv_id"] == "2501.00001"
        assert result["claims"] == 5
        assert result["links"] == 1
        assert result["input_tokens"] == 10
        assert result["output_tokens"] == 5
        assert session.query(Claim).count() == 5
        assert session.get(Entity, "bert") is not None
        assert session.query(EntityLink).filter_by(entity_key="bert").count() == 1

    def test_raises_when_paper_not_found(self, session, settings):
        llm = _stub_llm({"claims": CLAIMS_5, "entities": []})

        with pytest.raises(ValueError, match="nope"):
            enrich_paper("nope", session, llm, settings)

    def test_rerun_inserts_zero_new_claims(self, session, settings):
        _insert_paper(session)
        _insert_chunk(session, "2501.00001", "2501.00001::intro::0", "BERT improves accuracy on tasks.")
        llm = _stub_llm({"claims": CLAIMS_5, "entities": BERT_ENTITY})

        enrich_paper("2501.00001", session, llm, settings)
        result_2 = enrich_paper("2501.00001", session, llm, settings)

        assert result_2["claims"] == 0
        assert result_2["links"] == 0
        assert session.query(Claim).count() == 5
        assert session.query(EntityLink).filter_by(entity_key="bert").count() == 1

    def test_link_count_is_number_of_distinct_papers(self, session, settings):
        _insert_paper(session, arxiv_id="2501.00001")
        _insert_paper(session, arxiv_id="2501.00002")
        _insert_chunk(session, "2501.00001", "2501.00001::intro::0", "BERT improves accuracy.")
        _insert_chunk(session, "2501.00002", "2501.00002::intro::0", "BERT is widely used.")
        llm = _stub_llm({"claims": CLAIMS_5, "entities": BERT_ENTITY})

        enrich_paper("2501.00001", session, llm, settings)
        enrich_paper("2501.00002", session, llm, settings)

        entity = session.get(Entity, "bert")
        assert entity.link_count == 2

    def test_warning_from_extraction_is_passed_through(self, session, settings):
        _insert_paper(session)
        _insert_chunk(session, "2501.00001", "2501.00001::intro::0", "BERT improves accuracy on tasks.")
        few_claims = [{"text": "Only claim", "section_title": "Introduction"}]
        llm = _stub_llm({"claims": few_claims, "entities": []})

        result = enrich_paper("2501.00001", session, llm, settings)

        assert result["warning"] is not None

    def test_no_entities_at_all_skips_link_count_refresh(self, session, settings):
        _insert_paper(session, sections=[{"title": "Introduction", "text": "No named entities in here.", "level": 1}])
        session.query(Paper).filter_by(arxiv_id="2501.00001").update({"authors": []})
        session.flush()
        _insert_chunk(session, "2501.00001", "2501.00001::intro::0", "No named entities in here.")
        llm = _stub_llm({"claims": CLAIMS_5, "entities": []})

        result = enrich_paper("2501.00001", session, llm, settings)

        assert result["entities"] == 0
        assert result["links"] == 0


class TestEmbedAndIndexPaper:
    def test_excludes_bibliography_chunks(self, session):
        _insert_paper(session)
        _insert_chunk(session, "2501.00001", "2501.00001::intro::0", "Body text here", section_title="Introduction")
        _insert_chunk(session, "2501.00001", "2501.00001::refs::0", "Ref text", section_title="References")
        client = MagicMock()
        client.bulk.return_value = {"errors": False, "items": []}
        provider = FakeEmbeddingProvider(dimension=8)

        result = embed_and_index_paper("2501.00001", "evalv1", session, client, provider, default_pipeline_settings())

        assert result["chunks_indexed"] == 1
        assert result["failed"] == 0

    def test_indexes_claims_when_present(self, session):
        _insert_paper(session)
        _insert_chunk(session, "2501.00001", "2501.00001::intro::0", "Body text here", section_title="Introduction")
        session.add(Claim(claim_hash="h1", arxiv_id="2501.00001", claim_text="A claim.", section_title="Introduction"))
        session.flush()
        client = MagicMock()
        client.bulk.return_value = {"errors": False, "items": []}
        provider = FakeEmbeddingProvider(dimension=8)

        result = embed_and_index_paper("2501.00001", "evalv1", session, client, provider, default_pipeline_settings())

        assert result["claims_indexed"] == 1

    def test_reports_failures_via_returned_dict(self, session):
        _insert_paper(session)
        _insert_chunk(session, "2501.00001", "2501.00001::intro::0", "Body text here", section_title="Introduction")
        client = MagicMock()
        client.bulk.side_effect = RuntimeError("boom")
        provider = FakeEmbeddingProvider(dimension=8)

        result = embed_and_index_paper("2501.00001", "evalv1", session, client, provider, default_pipeline_settings())

        assert result["chunks_indexed"] == 0
        assert result["failed"] == 1
        assert "boom" in result["errors"][0]


class TestIndexEntitiesForCorpus:
    def test_builds_linked_arxiv_ids_and_chunk_ids(self, session):
        session.add(Entity(entity_key="bert", surface_forms=["BERT"], entity_type="method", link_count=2))
        session.add(EntityLink(entity_key="bert", arxiv_id="2501.00001", chunk_id="2501.00001::intro::0"))
        session.add(EntityLink(entity_key="bert", arxiv_id="2501.00002", chunk_id="2501.00002::intro::0"))
        session.flush()
        client = MagicMock()
        client.bulk.return_value = {"errors": False, "items": []}

        result = index_entities_for_corpus("evalv1", session, client)

        assert result == {"entities_indexed": 1, "failed": 0}
        doc = client.bulk.call_args.kwargs["body"][1]
        assert doc["linked_arxiv_ids"] == ["2501.00001", "2501.00002"]
        assert doc["linked_chunk_ids"] == ["2501.00001::intro::0", "2501.00002::intro::0"]

    def test_no_entities_indexes_nothing(self, session):
        client = MagicMock()

        result = index_entities_for_corpus("evalv1", session, client)

        assert result == {"entities_indexed": 0, "failed": 0}
        client.bulk.assert_not_called()


class TestReingestPreservesEnrichment:
    def test_reingesting_an_enriched_paper_keeps_its_claims(self, session, mocker, tmp_path):
        # claims carry a foreign key to papers; replacing the row would either
        # violate it or discard LLM output that cost money.
        mocker.patch("pipeline.stages.fetch_by_ids", return_value=[_metadata()])
        mocker.patch("pipeline.stages.parse_pdf", return_value=_pdf_content())
        mocker.patch("pipeline.stages._find_or_download_pdf", return_value=tmp_path / "p.pdf")
        settings = PipelineSettings(
            arxiv=ArxivSettings(), parser=ParserSettings(), chunking=ChunkingSettings(), enrichment=EnrichmentSettings()
        )

        parse_and_chunk_paper("2501.00001", "evalv1", tmp_path, session, settings)
        session.add(Claim(claim_hash="h1", arxiv_id="2501.00001", claim_text="a claim", section_title="Intro"))
        session.commit()

        parse_and_chunk_paper("2501.00001", "evalv1", tmp_path, session, settings)

        assert session.query(Claim).filter_by(arxiv_id="2501.00001").count() == 1
