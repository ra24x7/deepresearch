import pytest

from evals.solvability import AuditResult, QuoteMatch, audit_quote, normalize, quote_in_text


class TestNormalize:
    def test_ligature_is_expanded_to_ascii_letters(self):
        assert normalize("eﬃcient") == "efficient"

    def test_curly_quotes_and_apostrophes_become_ascii(self):
        assert normalize("“hello” it’s fine") == '"hello" it\'s fine'

    def test_em_and_en_dash_become_ascii_hyphen(self):
        assert normalize("a—b a–b") == "a-b a-b"

    def test_line_break_hyphenation_is_rejoined(self):
        assert normalize("trans-\nformer") == "transformer"

    def test_ordinary_hyphen_without_linebreak_is_preserved(self):
        assert normalize("state-of-the-art") == "state-of-the-art"

    def test_multiple_whitespace_and_newlines_collapse_to_single_space(self):
        assert normalize("hello   world\n\nfoo\t\tbar") == "hello world foo bar"

    def test_uppercase_text_is_lowercased(self):
        assert normalize("HELLO World") == "hello world"


class TestQuoteInText:
    def test_exact_match_survives_combined_typography_differences(self):
        quote = "we use transformers for efficient processing of long documents"
        text = (
            "prior work notes that we use trans-\nformers for eﬃcient processing "
            "of long documents, see “Figure 2”."
        )

        result = quote_in_text(quote, text)

        assert result.found is True
        assert result.match == "exact"

    def test_fuzzy_match_when_one_word_differs_slightly(self):
        quote = "we use transformers for efficient processing of long documents"
        text = "we use transformers for efficient processing of long document"

        result = quote_in_text(quote, text, threshold=95)

        assert result.found is True
        assert result.match == "fuzzy"

    def test_none_when_text_is_unrelated(self):
        quote = "we use transformers for efficient processing of long documents"
        text = "the quick brown fox jumps over the lazy dog"

        result = quote_in_text(quote, text)

        assert result.found is False
        assert result.match == "none"

    def test_returns_quote_match_result(self):
        result = quote_in_text("hello world", "hello world")

        assert isinstance(result, QuoteMatch)


class TestAuditQuote:
    QUOTE = "the model achieves state of the art results on the benchmark"

    def test_quote_wholly_inside_one_chunk_is_found_in_stage_b_with_its_chunk_id(self):
        raw_text = f"intro text. {self.QUOTE}. more text."
        chunks = [
            ("c1", "unrelated chunk text about something else"),
            ("c2", f"context before. {self.QUOTE}. context after."),
        ]

        result = audit_quote(self.QUOTE, raw_text, chunks)

        assert result.stage_a.found is True
        assert result.stage_a.match == "exact"
        assert result.stage_b_found is True
        assert result.stage_b_match == "exact"
        assert result.stage_b_chunk_id == "c2"

    def test_quote_straddling_two_chunks_is_a_chunk_boundary_failure(self):
        words = self.QUOTE.split()
        midpoint = len(words) // 2
        raw_text = self.QUOTE
        chunks = [
            ("c1", " ".join(words[:midpoint])),
            ("c2", " ".join(words[midpoint:])),
        ]

        result = audit_quote(self.QUOTE, raw_text, chunks)

        assert result.stage_a.found is True
        assert result.stage_b_found is False
        assert result.stage_b_chunk_id is None

    def test_exact_match_preferred_over_fuzzy_when_both_present(self):
        fuzzy_text = "the model achieves state of the art result on the benchmark"
        chunks = [
            ("c1", fuzzy_text),
            ("c2", self.QUOTE),
        ]

        result = audit_quote(self.QUOTE, self.QUOTE, chunks)

        assert result.stage_b_match == "exact"
        assert result.stage_b_chunk_id == "c2"

    def test_returns_audit_result(self):
        result = audit_quote("hello", "hello world", [("c1", "hello world")])

        assert isinstance(result, AuditResult)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestMathTokenizationRobustness:
    def test_unicode_minus_is_mapped_to_ascii_hyphen(self):
        assert normalize("[−47.4,−19.1]") == "[-47.4,-19.1]"

    def test_exact_match_despite_spaces_inserted_around_punctuation(self):
        quote = "the agent decides to act from {move, edge_search, backward, stop}."
        text = "at each turn, the agent decides to act from { move , edge _ search , backward , stop } . next"

        result = quote_in_text(quote, text)

        assert result.found is True
        assert result.match == "exact"

    def test_exact_match_despite_split_decimal_numbers(self):
        quote = "reduces recall by 32.8% (95% ci [-47.4,-19.1]; p < 10-4)"
        text = "reduces recall by 32.8% (95% ci [ -47 . 4 , -19 . 1 ] ; p < 10 - 4 ) overall"

        result = quote_in_text(quote, text)

        assert result.found is True
        assert result.match == "exact"
