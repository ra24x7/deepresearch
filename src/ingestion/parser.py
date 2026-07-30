from pathlib import Path

from config import ParserSettings
from ingestion.exceptions import ParserError, PDFTooLargeError
from ingestion.schemas import PaperSection, PdfContent

_SECTION_LABELS = {"title", "section_header"}
_FALLBACK_TITLE = "Full Text"
_PDF_HEADER = b"%PDF-"


def parse_pdf(path: Path, settings: ParserSettings) -> PdfContent:
    _validate_pdf_file(path)

    from docling.document_converter import DocumentConverter

    try:
        result = DocumentConverter().convert(str(path), max_num_pages=settings.max_pages)
    except Exception as exc:
        raise ParserError(f"Failed to parse PDF {path}: {exc}") from exc

    doc = result.document
    page_count = _page_count(doc)
    _validate_page_count(page_count, settings)

    return PdfContent(raw_text=doc.export_to_text(), sections=_map_sections(doc), page_count=page_count)


def _validate_pdf_file(path: Path) -> None:
    if not path.exists() or path.stat().st_size == 0:
        raise ParserError(f"PDF file is missing or empty: {path}")
    with path.open("rb") as fh:
        header = fh.read(len(_PDF_HEADER))
    if header != _PDF_HEADER:
        raise ParserError(f"File does not have a PDF header: {path}")


def _page_count(doc) -> int:
    return len(getattr(doc, "pages", ()))


def _validate_page_count(page_count: int, settings: ParserSettings) -> None:
    if page_count > settings.max_pages:
        raise PDFTooLargeError(f"PDF has {page_count} pages, exceeding limit of {settings.max_pages}")


def _map_sections(doc) -> tuple[PaperSection, ...]:
    sections: tuple[PaperSection, ...] = ()
    current_title = _FALLBACK_TITLE
    current_lines: tuple[str, ...] = ()

    for element in doc.texts:
        text = (getattr(element, "text", "") or "").strip()
        if not text:
            continue
        if getattr(element, "label", None) in _SECTION_LABELS:
            sections = _flush_section(sections, current_title, current_lines)
            current_title, current_lines = text, ()
            continue
        current_lines += (text,)

    return _flush_section(sections, current_title, current_lines)


def _flush_section(sections: tuple[PaperSection, ...], title: str, lines: tuple[str, ...]) -> tuple[PaperSection, ...]:
    if not lines:
        return sections
    return sections + (PaperSection(title=title, text="\n".join(lines), level=1),)
