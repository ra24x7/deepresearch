import pytest

from ingestion.ids import (
    pdf_filename,
    validate_arxiv_id,
    validate_category,
    validate_corpus,
    validate_pdf_url,
    validate_yyyymmdd,
)


class TestArxivId:
    @pytest.mark.parametrize("arxiv_id", ["2501.00001", "0704.0001", "2501.00001v3", "cs/0703001", "math.GT/0309136"])
    def test_accepts_modern_and_legacy_forms(self, arxiv_id):
        assert validate_arxiv_id(arxiv_id) == arxiv_id

    @pytest.mark.parametrize(
        "arxiv_id",
        ["../../etc/passwd", "2501.00001/../../secrets", "2501.00001; rm -rf /", "2501.00001\n", "*", ""],
    )
    def test_rejects_traversal_and_metacharacters(self, arxiv_id):
        with pytest.raises(ValueError):
            validate_arxiv_id(arxiv_id)


class TestPdfFilename:
    def test_modern_id_becomes_a_plain_filename(self):
        assert pdf_filename("2501.00001") == "2501.00001.pdf"

    def test_legacy_slash_is_flattened_so_it_stays_one_path_segment(self):
        assert pdf_filename("math.GT/0309136") == "math.GT_0309136.pdf"

    def test_rejects_an_id_that_would_escape_the_pdf_cache(self):
        with pytest.raises(ValueError):
            pdf_filename("../../../home/ubuntu/.ssh/authorized_keys")


class TestPdfUrl:
    @pytest.mark.parametrize(
        "url", ["https://arxiv.org/pdf/2501.00001v1", "https://export.arxiv.org/pdf/2501.00001", ""]
    )
    def test_accepts_https_arxiv_urls(self, url):
        assert validate_pdf_url(url) == url

    @pytest.mark.parametrize(
        "url",
        [
            "http://arxiv.org/pdf/2501.00001",
            "https://attacker.example/pdf/2501.00001",
            "https://arxiv.org.attacker.example/pdf/x",
            "file:///etc/passwd",
            "http://169.254.169.254/latest/meta-data/",
        ],
    )
    def test_rejects_non_arxiv_and_non_https_targets(self, url):
        with pytest.raises(ValueError):
            validate_pdf_url(url)


class TestCorpus:
    @pytest.mark.parametrize("corpus", ["corpusA", "rag-eval_v2", "0"])
    def test_accepts_plain_names(self, corpus):
        assert validate_corpus(corpus) == corpus

    @pytest.mark.parametrize("corpus", ["*", "a,b", "a/b", "../x", "-leading", "a" * 65, ""])
    def test_rejects_wildcards_separators_and_traversal(self, corpus):
        with pytest.raises(ValueError):
            validate_corpus(corpus)


class TestQueryParams:
    @pytest.mark.parametrize("category", ["cs.CL", "cs-cl", "math"])
    def test_accepts_arxiv_categories(self, category):
        assert validate_category(category) == category

    @pytest.mark.parametrize("category", ["cs.CL OR all:*", "cs.CL AND submittedDate:[* TO *]", "cs.CL "])
    def test_rejects_injected_query_clauses(self, category):
        with pytest.raises(ValueError):
            validate_category(category)

    def test_accepts_yyyymmdd(self):
        assert validate_yyyymmdd("20250101") == "20250101"

    @pytest.mark.parametrize("value", ["2025-01-01", "20250101 TO 20260101]", "*"])
    def test_rejects_anything_else(self, value):
        with pytest.raises(ValueError):
            validate_yyyymmdd(value)
