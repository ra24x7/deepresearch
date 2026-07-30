import re

from config import ChunkingSettings
from ingestion.schemas import ArxivMetadata, Chunk, PaperSection, PdfContent

_SLUG_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def chunk_paper(metadata: ArxivMetadata, pdf_content: PdfContent, settings: ChunkingSettings) -> list[Chunk]:
    sections = pdf_content.sections or (PaperSection(title="Full Text", text=pdf_content.raw_text, level=1),)

    chunks: tuple[Chunk, ...] = ()
    pending_text = ""
    pending_titles: tuple[str, ...] = ()

    for section in sections:
        text = f"{pending_text} {section.text}".strip() if pending_text else section.text
        titles = pending_titles + (section.title,)

        if len(text.split()) < settings.min_words:
            pending_text, pending_titles = text, titles
            continue

        section_title = " + ".join(titles)
        chunks += _process_section(text, section_title, metadata.arxiv_id, settings)
        pending_text, pending_titles = "", ()

    if pending_text:
        chunks = _merge_trailing(chunks, pending_text, pending_titles, metadata.arxiv_id, settings)

    return list(chunks)


def _process_section(text: str, section_title: str, arxiv_id: str, settings: ChunkingSettings) -> tuple[Chunk, ...]:
    if len(text.split()) <= settings.max_words:
        return (_make_chunk(arxiv_id, section_title, 0, text),)
    return _split_large_section(text, section_title, arxiv_id, settings)


def _split_large_section(text: str, section_title: str, arxiv_id: str, settings: ChunkingSettings) -> tuple[Chunk, ...]:
    words = text.split()
    step = settings.split_size - settings.overlap
    parts: tuple[Chunk, ...] = ()
    start = 0
    part_index = 0

    while start < len(words):
        end = min(start + settings.split_size, len(words))
        part_text = " ".join(words[start:end])
        parts += (_make_chunk(arxiv_id, section_title, part_index, part_text),)
        if end >= len(words):
            break
        start += step
        part_index += 1

    return parts


def _merge_trailing(
    chunks: tuple[Chunk, ...],
    pending_text: str,
    pending_titles: tuple[str, ...],
    arxiv_id: str,
    settings: ChunkingSettings,
) -> tuple[Chunk, ...]:
    if not chunks:
        section_title = " + ".join(pending_titles)
        return _process_section(pending_text, section_title, arxiv_id, settings)

    last = chunks[-1]
    merged_text = f"{last.text} {pending_text}".strip()
    merged = _make_chunk(arxiv_id, last.section_title, last.part_index, merged_text)
    return chunks[:-1] + (merged,)


def _make_chunk(arxiv_id: str, section_title: str, part_index: int, text: str) -> Chunk:
    chunk_id = f"{arxiv_id}::{_slugify(section_title)}::{part_index}"
    return Chunk(
        chunk_id=chunk_id,
        arxiv_id=arxiv_id,
        text=text,
        section_title=section_title,
        part_index=part_index,
        word_count=len(text.split()),
    )


def _slugify(title: str) -> str:
    return _SLUG_NON_ALNUM.sub("-", title.lower()).strip("-")
