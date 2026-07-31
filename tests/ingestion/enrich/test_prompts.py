from ingestion.enrich.prompts import build_enrichment_prompt


class TestBuildEnrichmentPrompt:
    def test_prompt_includes_title_and_abstract(self):
        prompt = build_enrichment_prompt("A Great Paper", "This paper studies X.", [], max_chars=2000)

        assert "A Great Paper" in prompt
        assert "This paper studies X." in prompt

    def test_prompt_specifies_strict_json_shape_and_entity_types(self):
        prompt = build_enrichment_prompt("T", "abstract", [], max_chars=2000)

        assert '"claims"' in prompt
        assert '"entities"' in prompt
        assert "method" in prompt
        assert "dataset" in prompt
        assert "metric" in prompt
        assert "task" in prompt

    def test_prompt_specifies_claim_count_range(self):
        prompt = build_enrichment_prompt("T", "abstract", [], max_chars=2000)

        assert "5" in prompt
        assert "15" in prompt

    def test_abstract_appears_before_any_section_in_the_prompt(self):
        sections = [("Introduction", "INTRO_TEXT " + "x" * 200)]

        prompt = build_enrichment_prompt("T", "ABSTRACT_TEXT", sections, max_chars=2000)

        assert prompt.index("ABSTRACT_TEXT") < prompt.index("INTRO_TEXT")

    def test_priority_sections_are_included_before_low_priority_ones_when_capped(self):
        sections = [
            ("Related Work", "RELATED_MARKER " + "r" * 300),
            ("Introduction", "INTRO_MARKER " + "i" * 300),
            ("Conclusion", "CONCLUSION_MARKER " + "c" * 300),
        ]

        prompt = build_enrichment_prompt("T", "short abstract", sections, max_chars=150)

        assert "INTRO_MARKER" in prompt
        assert "RELATED_MARKER" not in prompt

    def test_stable_order_preserved_among_sections_of_equal_priority(self):
        sections = [
            ("Appendix A", "APPENDIX_A_MARKER " + "a" * 50),
            ("Appendix B", "APPENDIX_B_MARKER " + "b" * 50),
        ]

        prompt = build_enrichment_prompt("T", "abstract", sections, max_chars=2000)

        assert prompt.index("APPENDIX_A_MARKER") < prompt.index("APPENDIX_B_MARKER")

    def test_total_selected_content_does_not_exceed_max_chars(self):
        sections = [("Method", "m" * 5000)]

        prompt = build_enrichment_prompt("T", "a" * 100, sections, max_chars=500)

        assert "m" * 5000 not in prompt

    def test_empty_sections_list_still_produces_valid_prompt_with_abstract_only(self):
        prompt = build_enrichment_prompt("T", "the abstract", [], max_chars=2000)

        assert "the abstract" in prompt
