from types import SimpleNamespace

import pytest

from config import ParserSettings
from ingestion.exceptions import ParserError, PDFTooLargeError
from ingestion.parser import _map_sections, _page_count, _validate_page_count, parse_pdf

SETTINGS = ParserSettings(max_pages=50)


def _elem(label: str, text: str) -> SimpleNamespace:
    return SimpleNamespace(label=label, text=text)


def _stub_doc(elements: list[SimpleNamespace]) -> SimpleNamespace:
    return SimpleNamespace(texts=elements)


class TestMapSections:
    def test_maps_docling_sections_by_title_and_section_header_labels(self):
        doc = _stub_doc(
            [
                _elem("section_header", "Introduction"),
                _elem("text", "This is the intro."),
                _elem("section_header", "Method"),
                _elem("text", "This is the method."),
            ]
        )

        sections = _map_sections(doc)

        assert [s.title for s in sections] == ["Introduction", "Method"]
        assert sections[0].text == "This is the intro."
        assert sections[1].text == "This is the method."

    def test_accumulates_multiple_body_text_elements_under_preceding_section(self):
        doc = _stub_doc(
            [
                _elem("section_header", "Introduction"),
                _elem("text", "First line."),
                _elem("text", "Second line."),
            ]
        )

        sections = _map_sections(doc)

        assert len(sections) == 1
        assert sections[0].text == "First line.\nSecond line."

    def test_falls_back_to_single_section_when_no_section_headers_present(self):
        doc = _stub_doc([_elem("text", "Just body text."), _elem("text", "More body text.")])

        sections = _map_sections(doc)

        assert len(sections) == 1
        assert sections[0].title == "Full Text"
        assert sections[0].text == "Just body text.\nMore body text."

    def test_skips_empty_text_elements(self):
        doc = _stub_doc(
            [
                _elem("section_header", "Introduction"),
                _elem("text", ""),
                _elem("text", "Real content."),
            ]
        )

        sections = _map_sections(doc)

        assert len(sections) == 1
        assert sections[0].text == "Real content."


class TestPageCount:
    def test_page_count_reads_length_of_doc_pages(self):
        doc = SimpleNamespace(pages={1: object(), 2: object(), 3: object()})

        assert _page_count(doc) == 3

    def test_page_count_is_zero_when_doc_has_no_pages_attribute(self):
        doc = SimpleNamespace()

        assert _page_count(doc) == 0


class TestValidatePageCount:
    def test_raises_when_page_count_exceeds_max_pages(self):
        with pytest.raises(PDFTooLargeError):
            _validate_page_count(51, SETTINGS)

    def test_does_not_raise_when_page_count_is_within_limit(self):
        _validate_page_count(50, SETTINGS)


class TestParsePdfFileValidation:
    def test_raises_typed_error_when_file_does_not_exist(self, tmp_path):
        missing = tmp_path / "missing.pdf"

        with pytest.raises(ParserError):
            parse_pdf(missing, SETTINGS)

    def test_raises_typed_error_when_file_is_empty(self, tmp_path):
        empty = tmp_path / "empty.pdf"
        empty.write_bytes(b"")

        with pytest.raises(ParserError):
            parse_pdf(empty, SETTINGS)

    def test_raises_typed_error_when_file_lacks_pdf_header(self, tmp_path):
        corrupt = tmp_path / "corrupt.pdf"
        corrupt.write_bytes(b"not a pdf at all")

        with pytest.raises(ParserError):
            parse_pdf(corrupt, SETTINGS)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
