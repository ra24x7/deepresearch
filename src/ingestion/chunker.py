import re

from config import ChunkingSettings
from ingestion.schemas import ArxivMetadata, Chunk, PaperSection, PdfContent

_SLUG_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def chunk_paper(metadata: ArxivMetadata, pdf_content: PdfContent, settings: ChunkingSettings) -> list[Chunk]:
    sections = pdf_content.sections or (PaperSection(title="Full Text", text=pdf_content.raw_text, level=1),)

    chunks: tuple[Chunk, ...] = ()
    slug_counts: dict[str, int] = {}
    pending_text = ""
    pending_titles: tuple[str, ...] = ()
    pending_pages: tuple[int, ...] = ()

    for section in sections:
        text = f"{pending_text} {section.text}".strip() if pending_text else section.text
        titles = pending_titles + (section.title,)
        pages = pending_pages + _section_pages(section)

        if len(text.split()) < settings.min_words:
            pending_text, pending_titles, pending_pages = text, titles, pages
            continue

        section_title = " + ".join(titles)
        slug = _unique_slug(section_title, slug_counts)
        chunks += _process_section(text, section_title, slug, metadata.arxiv_id, settings, _span(pages))
        pending_text, pending_titles, pending_pages = "", (), ()

    if pending_text:
        chunks = _merge_trailing(
            chunks, pending_text, pending_titles, _span(pending_pages), slug_counts, metadata.arxiv_id, settings
        )

    return list(chunks)


def _section_pages(section: PaperSection) -> tuple[int, ...]:
    return tuple(p for p in (section.page_start, section.page_end) if p is not None)


def _span(pages: tuple[int, ...]) -> tuple[int | None, int | None]:
    return (min(pages), max(pages)) if pages else (None, None)


def _unique_slug(section_title: str, slug_counts: dict[str, int]) -> str:
    # Real papers repeat section titles (e.g. per-figure "Answer" blocks); the
    # slug is part of the chunk_id primary key, so repeats must be suffixed.
    base = _SLUG_NON_ALNUM.sub("-", section_title.lower()).strip("-")
    occurrence = slug_counts.get(base, 0) + 1
    slug_counts[base] = occurrence
    return base if occurrence == 1 else f"{base}-{occurrence}"


def _process_section(
    text: str, section_title: str, slug: str, arxiv_id: str, settings: ChunkingSettings, span: tuple
) -> tuple[Chunk, ...]:
    if len(text.split()) <= settings.max_words:
        return (_make_chunk(arxiv_id, section_title, slug, 0, text, span),)
    return _split_large_section(text, section_title, slug, arxiv_id, settings, span)


def _split_large_section(
    text: str,
    section_title: str,
    slug: str,
    arxiv_id: str,
    settings: ChunkingSettings,
    span: tuple,
    first_part_index: int = 0,
) -> tuple[Chunk, ...]:
    words = text.split()
    step = settings.split_size - settings.overlap
    parts: tuple[Chunk, ...] = ()
    start = 0
    part_index = first_part_index

    while start < len(words):
        end = min(start + settings.split_size, len(words))
        part_text = " ".join(words[start:end])
        parts += (_make_chunk(arxiv_id, section_title, slug, part_index, part_text, span),)
        if end >= len(words):
            break
        start += step
        part_index += 1

    return parts


def _merge_trailing(
    chunks: tuple[Chunk, ...],
    pending_text: str,
    pending_titles: tuple[str, ...],
    pending_span: tuple,
    slug_counts: dict[str, int],
    arxiv_id: str,
    settings: ChunkingSettings,
) -> tuple[Chunk, ...]:
    if not chunks:
        section_title = " + ".join(pending_titles)
        slug = _unique_slug(section_title, slug_counts)
        return _process_section(pending_text, section_title, slug, arxiv_id, settings, pending_span)

    last = chunks[-1]
    last_slug = last.chunk_id.split("::")[1]
    merged_text = f"{last.text} {pending_text}".strip()
    span = _span(tuple(p for p in (last.page_start, last.page_end, *pending_span) if p is not None))
    if len(merged_text.split()) > settings.max_words:
        tail = _split_large_section(
            merged_text, last.section_title, last_slug, arxiv_id, settings, span, last.part_index
        )
        return chunks[:-1] + tail
    merged = _make_chunk(arxiv_id, last.section_title, last_slug, last.part_index, merged_text, span)
    return chunks[:-1] + (merged,)


def _make_chunk(
    arxiv_id: str, section_title: str, slug: str, part_index: int, text: str, span: tuple
) -> Chunk:
    return Chunk(
        chunk_id=f"{arxiv_id}::{slug}::{part_index}",
        arxiv_id=arxiv_id,
        text=text,
        section_title=section_title,
        part_index=part_index,
        word_count=len(text.split()),
        page_start=span[0],
        page_end=span[1],
    )
