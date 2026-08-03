from datetime import date

from config import EnrichmentSettings
from ingestion.enrich.claims import extract_claims_and_entities
from ingestion.schemas import ArxivMetadata
from llm.bedrock import Usage

SETTINGS = EnrichmentSettings(prompt_max_chars=2000)


def _metadata(arxiv_id: str = "2501.00001") -> ArxivMetadata:
    return ArxivMetadata(
        arxiv_id=arxiv_id,
        title="A Great Paper",
        authors=("Jane Doe",),
        abstract="An abstract.",
        categories=("cs.AI",),
        published=date(2025, 1, 1),
        pdf_url="https://arxiv.org/pdf/2501.00001",
    )


def _claim(text: str, section_title: str = "Introduction") -> dict:
    return {"text": text, "section_title": section_title}


_DEFAULT_USAGE = Usage(input_tokens=100, output_tokens=50)


def _stub_llm(data: dict, usage: Usage = _DEFAULT_USAGE):
    def _invoke(prompt: str) -> tuple[dict, Usage]:
        _invoke.last_prompt = prompt
        return data, usage

    return _invoke


class TestExtractClaims:
    def test_returns_valid_claims_with_hash_and_arxiv_id_when_count_in_range(self):
        data = {"claims": [_claim(f"Claim number {i}") for i in range(6)], "entities": []}
        llm = _stub_llm(data)

        result = extract_claims_and_entities(_metadata("2501.00001"), [], llm, SETTINGS)

        assert len(result.claims) == 6
        assert result.warning is None
        assert all(c.arxiv_id == "2501.00001" for c in result.claims)
        assert all(len(c.claim_hash) == 64 for c in result.claims)

    def test_claim_hash_is_stable_across_case_and_whitespace_differences(self):
        base_claims = [_claim(f"Claim number {i}") for i in range(1, 5)]
        data_a = {"claims": [_claim("The Model Improves Accuracy")] + base_claims, "entities": []}
        data_b = {"claims": [_claim("the   model improves accuracy")] + base_claims, "entities": []}

        result_a = extract_claims_and_entities(_metadata(), [], _stub_llm(data_a), SETTINGS)
        result_b = extract_claims_and_entities(_metadata(), [], _stub_llm(data_b), SETTINGS)

        assert result_a.claims[0].claim_hash == result_b.claims[0].claim_hash

    def test_more_than_15_claims_are_truncated_to_15_with_warning(self):
        data = {"claims": [_claim(f"Claim number {i}") for i in range(20)], "entities": []}

        result = extract_claims_and_entities(_metadata(), [], _stub_llm(data), SETTINGS)

        assert len(result.claims) == 15
        assert result.warning is not None
        assert "15" in result.warning

    def test_fewer_than_5_claims_are_kept_with_warning_and_no_exception(self):
        data = {"claims": [_claim(f"Claim number {i}") for i in range(3)], "entities": []}

        result = extract_claims_and_entities(_metadata(), [], _stub_llm(data), SETTINGS)

        assert len(result.claims) == 3
        assert result.warning is not None

    def test_claims_missing_required_fields_are_skipped(self):
        data = {
            "claims": [
                {"text": "", "section_title": "Intro"},
                {"text": "Valid claim one"},
                *[_claim(f"Claim number {i}") for i in range(5)],
            ],
            "entities": [],
        }

        result = extract_claims_and_entities(_metadata(), [], _stub_llm(data), SETTINGS)

        assert len(result.claims) == 5

    def test_usage_from_llm_invoke_json_is_returned_on_result(self):
        data = {"claims": [_claim(f"Claim number {i}") for i in range(5)], "entities": []}
        llm = _stub_llm(data, usage=Usage(input_tokens=222, output_tokens=111))

        result = extract_claims_and_entities(_metadata(), [], llm, SETTINGS)

        assert result.usage == Usage(input_tokens=222, output_tokens=111)


class TestExtractEntities:
    def test_returns_llm_entities_with_normalized_entity_key(self):
        data = {
            "claims": [_claim(f"Claim number {i}") for i in range(5)],
            "entities": [{"surface_form": "BERT", "entity_type": "method"}],
        }

        result = extract_claims_and_entities(_metadata(), [], _stub_llm(data), SETTINGS)

        assert len(result.entities) == 1
        assert result.entities[0].entity_key == "bert"
        assert result.entities[0].surface_form == "BERT"
        assert result.entities[0].entity_type == "method"

    def test_entities_are_deduped_by_normalized_surface_form_keeping_first(self):
        data = {
            "claims": [_claim(f"Claim number {i}") for i in range(5)],
            "entities": [
                {"surface_form": "BERT", "entity_type": "method"},
                {"surface_form": "bert", "entity_type": "method"},
            ],
        }

        result = extract_claims_and_entities(_metadata(), [], _stub_llm(data), SETTINGS)

        assert len(result.entities) == 1
        assert result.entities[0].surface_form == "BERT"

    def test_entities_missing_required_fields_are_skipped(self):
        data = {
            "claims": [_claim(f"Claim number {i}") for i in range(5)],
            "entities": [{"surface_form": "BERT"}, {"entity_type": "method"}],
        }

        result = extract_claims_and_entities(_metadata(), [], _stub_llm(data), SETTINGS)

        assert result.entities == ()


class TestPromptConstruction:
    def test_prompt_passed_to_llm_includes_title_and_abstract(self):
        data = {"claims": [_claim(f"Claim number {i}") for i in range(5)], "entities": []}
        llm = _stub_llm(data)

        extract_claims_and_entities(_metadata(), [], llm, SETTINGS)

        assert "A Great Paper" in llm.last_prompt
        assert "An abstract." in llm.last_prompt


class TestClaimHashPaperScoping:
    def test_identical_claim_text_in_different_papers_gets_different_hashes(self):
        data = {"claims": [_claim("This paper proposes a novel method.")] * 5, "entities": []}

        result_a = extract_claims_and_entities(_metadata("2501.00001"), [], _stub_llm(data), SETTINGS)
        result_b = extract_claims_and_entities(_metadata("2501.00002"), [], _stub_llm(data), SETTINGS)

        assert result_a.claims[0].claim_hash != result_b.claims[0].claim_hash
