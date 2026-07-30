from pathlib import Path

from config import ParserSettings
from ingestion.exceptions import ParserError, PDFTooLargeError
from ingestion.schemas import PaperSection, PdfContent

_SECTION_LABELS = {"title", "section_header"}
_FALLBACK_TITLE = "Full Text"
_PDF_HEADER = b"%PDF-"
_BYTES_PER_MB = 1024 * 1024


def parse_pdf(path: Path, settings: ParserSettings) -> PdfContent:
    _validate_pdf_file(path, settings)

    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    # do_ocr defaults off: arXiv PDFs are born-digital, and OCR pulls model
    # downloads into read-only site-packages inside the container.
    pipeline_options = PdfPipelineOptions(do_ocr=settings.do_ocr, do_table_structure=settings.do_table_structure)
    converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)})
    try:
        result = converter.convert(str(path), max_num_pages=settings.max_pages)
    except Exception as exc:
        raise ParserError(f"Failed to parse PDF {path}: {exc}") from exc

    doc = result.document
    page_count = _page_count(doc)
    _validate_page_count(page_count, settings)

    return PdfContent(raw_text=doc.export_to_text(), sections=_map_sections(doc), page_count=page_count)


def _validate_pdf_file(path: Path, settings: ParserSettings) -> None:
    if not path.exists() or path.stat().st_size == 0:
        raise ParserError(f"PDF file is missing or empty: {path}")
    size_mb = path.stat().st_size / _BYTES_PER_MB
    if size_mb > settings.max_file_size_mb:
        raise PDFTooLargeError(f"PDF is {size_mb:.1f} MB, exceeding limit of {settings.max_file_size_mb} MB: {path}")
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
