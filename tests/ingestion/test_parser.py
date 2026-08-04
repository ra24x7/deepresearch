from types import SimpleNamespace

import pytest

from config import ParserSettings
from ingestion.exceptions import ParserError, PDFTooLargeError
from ingestion.parser import _map_sections, _page_count, _validate_page_count, parse_pdf

SETTINGS = ParserSettings(max_pages=50)


def _elem(label: str, text: str, page: int | None = 1) -> SimpleNamespace:
    prov = [SimpleNamespace(page_no=page)] if page is not None else []
    return SimpleNamespace(label=label, text=text, prov=prov)


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


class TestFileSizeCap:
    def test_oversized_pdf_raises_pdf_too_large(self, tmp_path):
        big = tmp_path / "big.pdf"
        big.write_bytes(b"%PDF-" + b"x" * (2 * 1024 * 1024))

        with pytest.raises(PDFTooLargeError, match="MB"):
            parse_pdf(big, ParserSettings(max_pages=50, max_file_size_mb=1))


class TestCaptionDeferral:
    def test_caption_between_body_elements_is_moved_to_section_end(self):
        doc = _stub_doc(
            [
                _elem("section_header", "5.3 Failure Analysis"),
                _elem("text", "the majority of failures stem from reasoning"),
                _elem("caption", "Figure 5: failure mode distribution."),
                _elem("text", "chain errors. among these, entity confusion is common."),
            ]
        )

        sections = _map_sections(doc)

        assert len(sections) == 1
        body = sections[0].text
        assert "reasoning\nchain errors" in body
        assert body.endswith("Figure 5: failure mode distribution.")

    def test_caption_only_section_is_still_flushed(self):
        doc = _stub_doc([_elem("section_header", "Figures"), _elem("caption", "Figure 1: overview.")])

        sections = _map_sections(doc)

        assert len(sections) == 1
        assert sections[0].text == "Figure 1: overview."


class TestNulByteSanitisation:
    def test_nul_bytes_are_stripped_from_section_text(self):
        doc = _stub_doc([_elem("section_header", "Intro"), _elem("text", "before\x00after")])

        sections = _map_sections(doc)

        assert "\x00" not in sections[0].text
        assert sections[0].text == "beforeafter"

    def test_nul_bytes_are_stripped_from_section_titles(self):
        doc = _stub_doc([_elem("section_header", "Ti\x00tle"), _elem("text", "body text here")])

        sections = _map_sections(doc)

        assert sections[0].title == "Title"


class TestPageProvenance:
    def test_section_records_first_and_last_page_of_its_elements(self):
        doc = _stub_doc(
            [
                _elem("section_header", "Method", page=3),
                _elem("text", "body on page three", page=3),
                _elem("text", "body continues on page four", page=4),
            ]
        )

        sections = _map_sections(doc)

        assert (sections[0].page_start, sections[0].page_end) == (3, 4)

    def test_pages_are_none_when_docling_supplies_no_provenance(self):
        doc = _stub_doc([_elem("section_header", "Method", page=None), _elem("text", "body", page=None)])

        sections = _map_sections(doc)

        assert sections[0].page_start is None and sections[0].page_end is None

    def test_deferred_caption_still_contributes_its_page(self):
        doc = _stub_doc(
            [
                _elem("section_header", "Results", page=5),
                _elem("text", "body text here", page=5),
                _elem("caption", "Figure 2: a caption on page seven", page=7),
            ]
        )

        sections = _map_sections(doc)

        assert (sections[0].page_start, sections[0].page_end) == (5, 7)
