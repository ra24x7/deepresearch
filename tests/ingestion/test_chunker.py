from datetime import date
from itertools import pairwise

import pytest

from config import ChunkingSettings
from ingestion.chunker import chunk_paper
from ingestion.schemas import ArxivMetadata, Chunk, PaperSection, PdfContent

SETTINGS = ChunkingSettings(min_words=100, max_words=800, split_size=600, overlap=100)


def _metadata(arxiv_id: str = "2501.00001") -> ArxivMetadata:
    return ArxivMetadata(
        arxiv_id=arxiv_id,
        title="A Paper",
        authors=("Jane Doe",),
        abstract="An abstract.",
        categories=("cs.AI",),
        published=date(2025, 1, 1),
        pdf_url="https://arxiv.org/pdf/2501.00001",
    )


def _words(n: int, prefix: str = "word") -> str:
    return " ".join(f"{prefix}{i}" for i in range(n))


def _pdf_content(sections: tuple[PaperSection, ...], raw_text: str = "") -> PdfContent:
    return PdfContent(raw_text=raw_text, sections=sections, page_count=1)


class TestSectionSizeBoundaries:
    def test_section_with_99_words_is_treated_as_small_and_merged_forward(self):
        small = PaperSection(title="Intro", text=_words(99), level=1)
        normal = PaperSection(title="Method", text=_words(200), level=1)
        content = _pdf_content((small, normal))

        chunks = chunk_paper(_metadata(), content, SETTINGS)

        assert len(chunks) == 1
        assert chunks[0].section_title == "Intro + Method"
        assert chunks[0].word_count == 299

    def test_section_with_exactly_100_words_becomes_its_own_single_chunk(self):
        section = PaperSection(title="Method", text=_words(100), level=1)
        content = _pdf_content((section,))

        chunks = chunk_paper(_metadata(), content, SETTINGS)

        assert len(chunks) == 1
        assert chunks[0].word_count == 100
        assert chunks[0].section_title == "Method"

    def test_section_with_exactly_800_words_becomes_its_own_single_chunk(self):
        section = PaperSection(title="Method", text=_words(800), level=1)
        content = _pdf_content((section,))

        chunks = chunk_paper(_metadata(), content, SETTINGS)

        assert len(chunks) == 1
        assert chunks[0].word_count == 800

    def test_section_with_801_words_is_split_into_two_parts(self):
        section = PaperSection(title="Method", text=_words(801), level=1)
        content = _pdf_content((section,))

        chunks = chunk_paper(_metadata(), content, SETTINGS)

        assert len(chunks) == 2
        assert all(c.section_title == "Method" for c in chunks)
        assert [c.part_index for c in chunks] == [0, 1]


class TestSmallSectionMerging:
    def test_leading_small_section_merges_forward_into_next_section(self):
        small = PaperSection(title="Header", text=_words(20), level=1)
        normal = PaperSection(title="Intro", text=_words(150), level=1)
        content = _pdf_content((small, normal))

        chunks = chunk_paper(_metadata(), content, SETTINGS)

        assert len(chunks) == 1
        assert chunks[0].word_count == 170
        assert chunks[0].text.startswith(_words(20).split()[0])

    def test_trailing_small_section_merges_backward_into_previous_chunk(self):
        normal = PaperSection(title="Conclusion", text=_words(150), level=1)
        small = PaperSection(title="Acknowledgements", text=_words(15), level=1)
        content = _pdf_content((normal, small))

        chunks = chunk_paper(_metadata(), content, SETTINGS)

        assert len(chunks) == 1
        assert chunks[0].section_title == "Conclusion"
        assert chunks[0].word_count == 165
        assert chunks[0].text.endswith(_words(15).split()[-1])

    def test_all_small_sections_with_no_qualifying_section_merge_into_one_chunk(self):
        s1 = PaperSection(title="A", text=_words(10), level=1)
        s2 = PaperSection(title="B", text=_words(10), level=1)
        content = _pdf_content((s1, s2))

        chunks = chunk_paper(_metadata(), content, SETTINGS)

        assert len(chunks) == 1
        assert chunks[0].word_count == 20
        assert chunks[0].section_title == "A + B"


class TestEmptySectionsFallback:
    def test_empty_sections_falls_back_to_chunking_whole_raw_text(self):
        content = _pdf_content((), raw_text=_words(150))

        chunks = chunk_paper(_metadata(), content, SETTINGS)

        assert len(chunks) == 1
        assert chunks[0].word_count == 150


class TestOverlapCorrectness:
    def test_each_subsequent_part_starts_with_last_overlap_words_of_previous_part(self):
        section = PaperSection(title="Method", text=_words(1500), level=1)
        content = _pdf_content((section,))

        chunks = chunk_paper(_metadata(), content, SETTINGS)

        assert len(chunks) >= 2
        for prev, nxt in pairwise(chunks):
            prev_words = prev.text.split()
            next_words = nxt.text.split()
            assert prev_words[-SETTINGS.overlap :] == next_words[: SETTINGS.overlap]

    def test_split_part_word_counts_respect_split_size(self):
        section = PaperSection(title="Method", text=_words(1500), level=1)
        content = _pdf_content((section,))

        chunks = chunk_paper(_metadata(), content, SETTINGS)

        for chunk in chunks[:-1]:
            assert chunk.word_count == SETTINGS.split_size


class TestDeterminismAndImmutability:
    def test_two_runs_with_identical_input_produce_identical_output(self):
        section = PaperSection(title="Method", text=_words(900), level=1)
        content = _pdf_content((section,))
        metadata = _metadata()

        first = chunk_paper(metadata, content, SETTINGS)
        second = chunk_paper(metadata, content, SETTINGS)

        assert first == second

    def test_input_metadata_and_pdf_content_are_unchanged_after_call(self):
        section = PaperSection(title="Method", text=_words(900), level=1)
        content = _pdf_content((section,))
        metadata = _metadata()

        metadata_before = metadata.model_dump()
        content_before = content.model_dump()

        chunk_paper(metadata, content, SETTINGS)

        assert metadata.model_dump() == metadata_before
        assert content.model_dump() == content_before

    def test_return_value_is_a_plain_list_of_chunk_instances(self):
        section = PaperSection(title="Method", text=_words(200), level=1)
        content = _pdf_content((section,))

        chunks = chunk_paper(_metadata(), content, SETTINGS)

        assert isinstance(chunks, list)
        assert all(isinstance(c, Chunk) for c in chunks)


class TestChunkIdStability:
    def test_chunk_id_is_arxiv_id_section_slug_and_part_index(self):
        section = PaperSection(title="Related Work", text=_words(200), level=1)
        content = _pdf_content((section,))

        chunks = chunk_paper(_metadata("2501.99999"), content, SETTINGS)

        assert chunks[0].chunk_id == "2501.99999::related-work::0"

    def test_chunk_ids_are_stable_and_unique_across_split_parts(self):
        section = PaperSection(title="Method", text=_words(801), level=1)
        content = _pdf_content((section,))

        chunks = chunk_paper(_metadata("2501.00002"), content, SETTINGS)

        assert [c.chunk_id for c in chunks] == [
            "2501.00002::method::0",
            "2501.00002::method::1",
        ]

    def test_chunk_id_slugifies_titles_with_spaces_and_punctuation(self):
        section = PaperSection(title="Results & Discussion!", text=_words(150), level=1)
        content = _pdf_content((section,))

        chunks = chunk_paper(_metadata("2501.00003"), content, SETTINGS)

        assert chunks[0].chunk_id == "2501.00003::results-discussion::0"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestTrailingMergeSizeCeiling:
    def test_trailing_merge_that_exceeds_max_words_is_resplit(self):
        big = PaperSection(title="Method", text=_words(800), level=1)
        tail = PaperSection(title="Ack", text=_words(99, prefix="ack"), level=1)
        content = _pdf_content((big, tail))

        chunks = chunk_paper(_metadata(), content, SETTINGS)

        assert all(c.word_count <= SETTINGS.max_words for c in chunks)
        assert len(chunks) == 2
        assert [c.part_index for c in chunks] == [0, 1]
        joined = set(" ".join(c.text for c in chunks).split())
        assert "ack98" in joined and "word799" in joined

    def test_trailing_merge_within_max_words_stays_single_chunk(self):
        big = PaperSection(title="Method", text=_words(700), level=1)
        tail = PaperSection(title="Ack", text=_words(50, prefix="ack"), level=1)
        content = _pdf_content((big, tail))

        chunks = chunk_paper(_metadata(), content, SETTINGS)

        assert len(chunks) == 1
        assert chunks[0].word_count == 750


class TestChunkingSettingsValidation:
    def test_overlap_equal_to_split_size_is_rejected(self):
        with pytest.raises(ValueError, match="overlap"):
            ChunkingSettings(min_words=10, max_words=50, split_size=100, overlap=100)

    def test_overlap_greater_than_split_size_is_rejected(self):
        with pytest.raises(ValueError, match="overlap"):
            ChunkingSettings(min_words=10, max_words=50, split_size=100, overlap=150)


class TestSettingsAdoptions:
    def test_settings_are_frozen(self):
        with pytest.raises(ValueError):
            SETTINGS.max_words = 900

    def test_postgres_dsn_scheme_is_validated(self):
        from config import PostgresSettings

        with pytest.raises(ValueError, match="postgresql"):
            PostgresSettings(dsn="mysql://nope")


class TestDuplicateSectionTitles:
    def test_two_sections_with_same_title_get_distinct_chunk_ids(self):
        first = PaperSection(title="Answer", text=_words(150), level=1)
        second = PaperSection(title="Answer", text=_words(200, prefix="other"), level=1)
        content = _pdf_content((first, second))

        chunks = chunk_paper(_metadata(), content, SETTINGS)

        ids = [c.chunk_id for c in chunks]
        assert len(ids) == len(set(ids))
        assert ids[0] == "2501.00001::answer::0"
        assert ids[1] == "2501.00001::answer-2::0"

    def test_second_duplicate_section_splits_keep_consistent_suffix(self):
        first = PaperSection(title="Answer", text=_words(150), level=1)
        second = PaperSection(title="Answer", text=_words(900, prefix="other"), level=1)
        content = _pdf_content((first, second))

        chunks = chunk_paper(_metadata(), content, SETTINGS)

        ids = [c.chunk_id for c in chunks]
        assert len(ids) == len(set(ids))
        assert "2501.00001::answer-2::0" in ids
        assert "2501.00001::answer-2::1" in ids
