import pytest

from search.filters import is_indexable_section


class TestIsIndexableSection:
    @pytest.mark.parametrize(
        "title",
        ["References", "REFERENCES", "VIII. REFERENCES", "Bibliography", "8 References"],
    )
    def test_purely_bibliographic_sections_are_excluded(self, title):
        assert is_indexable_section(title) is False

    @pytest.mark.parametrize(
        "title",
        [
            "Conclusion + References",
            "7 Limitations + References",
            "10 Acknowledgment + Ethics Statement + References",
        ],
    )
    def test_merged_sections_keeping_real_content_are_indexed(self, title):
        assert is_indexable_section(title) is True

    def test_acm_reference_format_is_not_treated_as_a_bibliography(self):
        # "ACMReference" has no word boundary before "Reference"; this chunk carries the Introduction.
        assert is_indexable_section("CCS Concepts + Keywords + ACMReference Format: + 1 Introduction") is True

    @pytest.mark.parametrize("title", ["Acknowledgments", "Acknowledgements", "Funding"])
    def test_acknowledgments_stay_indexed(self, title):
        assert is_indexable_section(title) is True

    @pytest.mark.parametrize("title", ["3 Methodology", "Abstract", "4.2 Main Results"])
    def test_ordinary_sections_are_indexed(self, title):
        assert is_indexable_section(title) is True
