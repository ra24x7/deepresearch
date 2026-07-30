from datetime import date

from pydantic import BaseModel, ConfigDict


class ArxivMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    arxiv_id: str
    title: str
    authors: tuple[str, ...]
    abstract: str
    categories: tuple[str, ...]
    published: date
    pdf_url: str


class PaperSection(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str
    text: str
    level: int = 1


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
