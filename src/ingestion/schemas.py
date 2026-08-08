from datetime import date

from pydantic import BaseModel, ConfigDict, field_validator

from ingestion.ids import validate_arxiv_id, validate_pdf_url


class ArxivMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    arxiv_id: str
    title: str
    authors: tuple[str, ...]
    abstract: str
    categories: tuple[str, ...]
    published: date
    pdf_url: str

    # Both fields arrive from an arXiv response body and then reach the
    # filesystem and the network, so they are validated on construction.
    @field_validator("arxiv_id")
    @classmethod
    def _check_arxiv_id(cls, value: str) -> str:
        return validate_arxiv_id(value)

    @field_validator("pdf_url")
    @classmethod
    def _check_pdf_url(cls, value: str) -> str:
        return validate_pdf_url(value)


class PaperSection(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str
    text: str
    level: int = 1
    page_start: int | None = None
    page_end: int | None = None


class PdfContent(BaseModel):
    model_config = ConfigDict(frozen=True)

    raw_text: str
    sections: tuple[PaperSection, ...] = ()
    page_count: int


class Chunk(BaseModel):
    model_config = ConfigDict(frozen=True)

    chunk_id: str
    arxiv_id: str
    text: str
    section_title: str
    part_index: int
    word_count: int
    page_start: int | None = None
    page_end: int | None = None
