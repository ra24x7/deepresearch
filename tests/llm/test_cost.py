import pytest
from pydantic import ValidationError

from llm.bedrock import Usage
from llm.cost import EMBED_V4, HAIKU_4_5, RERANK_3_5, SONNET_4_6, CostLedger


class TestEmptyLedger:
    def test_starts_at_zero(self):
        ledger = CostLedger()

        assert ledger.total_usd == 0.0
        assert ledger.unpriced == ()


class TestImmutability:
    def test_add_returns_a_new_ledger_and_leaves_the_original_alone(self):
        original = CostLedger()

        updated = original.add(Usage(input_tokens=1_000_000, output_tokens=0), HAIKU_4_5)

        assert original.total_usd == 0.0
        assert updated.total_usd == pytest.approx(1.00)

    def test_the_ledger_is_frozen(self):
        ledger = CostLedger()

        with pytest.raises(ValidationError):
            ledger.rerank_queries = 5


class TestTokenPricing:
    def test_haiku_is_priced_at_one_and_five_per_million(self):
        ledger = CostLedger().add(Usage(input_tokens=1_000_000, output_tokens=1_000_000), HAIKU_4_5)

        assert ledger.total_usd == pytest.approx(1.00 + 5.00)

    def test_sonnet_is_priced_at_three_and_fifteen_per_million(self):
        ledger = CostLedger().add(Usage(input_tokens=1_000_000, output_tokens=1_000_000), SONNET_4_6)

        assert ledger.total_usd == pytest.approx(3.00 + 15.00)

    def test_models_accumulate_separately_and_sum(self):
        ledger = (
            CostLedger()
            .add(Usage(input_tokens=1_000_000, output_tokens=0), HAIKU_4_5)
            .add(Usage(input_tokens=1_000_000, output_tokens=0), SONNET_4_6)
        )

        assert ledger.total_usd == pytest.approx(1.00 + 3.00)

    def test_repeated_calls_to_one_model_accumulate(self):
        ledger = (
            CostLedger()
            .add(Usage(input_tokens=500_000, output_tokens=0), HAIKU_4_5)
            .add(Usage(input_tokens=500_000, output_tokens=0), HAIKU_4_5)
        )

        assert ledger.total_usd == pytest.approx(1.00)


class TestRerankPricing:
    def test_a_request_under_the_document_cap_is_one_query(self):
        ledger = CostLedger().add_rerank(documents=60)

        assert ledger.rerank_queries == 1

    def test_aws_worked_example_350_documents_is_four_queries(self):
        # straight from the Bedrock pricing footnote: "if a request contains
        # 350 documents, it will be treated as 4 queries"
        ledger = CostLedger().add_rerank(documents=350)

        assert ledger.rerank_queries == 4

    def test_priced_at_two_dollars_per_thousand_queries(self):
        ledger = CostLedger()
        for _ in range(1_000):
            ledger = ledger.add_rerank(documents=1)

        assert ledger.total_usd == pytest.approx(2.00)


class TestUnpricedComponents:
    def test_embed_calls_are_counted_but_not_priced(self):
        ledger = CostLedger().add_embed(calls=136)

        assert ledger.embed_calls == 136
        assert ledger.total_usd == 0.0

    def test_embed_usage_names_itself_as_unpriced(self):
        ledger = CostLedger().add_embed(calls=1)

        assert EMBED_V4 in ledger.unpriced

    def test_no_embed_usage_means_nothing_unpriced(self):
        ledger = CostLedger().add(Usage(input_tokens=10, output_tokens=10), HAIKU_4_5)

        assert ledger.unpriced == ()

    def test_an_unrated_model_is_flagged_rather_than_silently_free(self):
        # the failure this guards: a new model gets wired in, has no rate, and
        # contributes $0.00 to a cost-per-query number nobody re-checks
        ledger = CostLedger().add(Usage(input_tokens=1_000_000, output_tokens=0), "some.new.model")

        assert "some.new.model" in ledger.unpriced
        assert ledger.total_usd == 0.0


class TestFlatTotals:
    def test_input_and_output_tokens_sum_across_models(self):
        # ingestion_runs stores one flat total per run, so the aggregate has to
        # survive the move to per-model accounting
        ledger = (
            CostLedger()
            .add(Usage(input_tokens=100, output_tokens=10), HAIKU_4_5)
            .add(Usage(input_tokens=200, output_tokens=20), SONNET_4_6)
        )

        assert ledger.input_tokens == 300
        assert ledger.output_tokens == 30

    def test_an_empty_ledger_reports_zero_tokens(self):
        assert CostLedger().input_tokens == 0
        assert CostLedger().output_tokens == 0


class TestPerPaper:
    def test_divides_the_total_by_the_paper_count(self):
        ledger = CostLedger().add(Usage(input_tokens=1_000_000, output_tokens=0), HAIKU_4_5)

        assert ledger.per_paper_usd(4) == pytest.approx(0.25)

    def test_raises_on_zero_papers(self):
        ledger = CostLedger().add(Usage(input_tokens=1_000_000, output_tokens=0), HAIKU_4_5)

        with pytest.raises(ValueError):
            ledger.per_paper_usd(0)


class TestModelIdentifiers:
    def test_the_constants_match_the_ids_the_project_actually_calls(self):
        assert HAIKU_4_5 == "global.anthropic.claude-haiku-4-5-20251001-v1:0"
        assert SONNET_4_6 == "global.anthropic.claude-sonnet-4-6"
        assert RERANK_3_5 == "cohere.rerank-v3-5:0"
        assert EMBED_V4 == "global.cohere.embed-v4:0"


class TestPromptCachePricing:
    """A cached run whose cache tokens are not priced reports a saving it did
    not make. Anthropic bills a cache write at 1.25x the input rate and a cache
    read at 0.1x -- both unverified against Bedrock, like every rate here.
    """

    def test_a_cache_write_costs_a_quarter_more_than_plain_input(self):
        ledger = CostLedger().add(
            Usage(input_tokens=0, output_tokens=0, cache_write_tokens=1_000_000), SONNET_4_6
        )

        assert ledger.total_usd == pytest.approx(3.00 * 1.25)

    def test_a_cache_read_costs_a_tenth_of_plain_input(self):
        ledger = CostLedger().add(
            Usage(input_tokens=0, output_tokens=0, cache_read_tokens=1_000_000), SONNET_4_6
        )

        assert ledger.total_usd == pytest.approx(3.00 * 0.10)

    def test_cache_tokens_are_reported_separately_from_plain_input(self):
        ledger = CostLedger().add(
            Usage(input_tokens=100, output_tokens=10, cache_read_tokens=1_000, cache_write_tokens=50),
            SONNET_4_6,
        )

        totals = ledger.tokens_by_model[SONNET_4_6]
        assert (totals.input_tokens, totals.cache_read_tokens, totals.cache_write_tokens) == (100, 1_000, 50)

    def test_cache_tokens_accumulate_across_calls(self):
        ledger = (
            CostLedger()
            .add(Usage(input_tokens=0, output_tokens=0, cache_read_tokens=500_000), SONNET_4_6)
            .add(Usage(input_tokens=0, output_tokens=0, cache_read_tokens=500_000), SONNET_4_6)
        )

        assert ledger.cache_read_tokens == 1_000_000

    def test_a_usage_without_cache_fields_still_prices(self):
        # every existing call site builds Usage with two fields
        ledger = CostLedger().add(Usage(input_tokens=1_000_000, output_tokens=0), SONNET_4_6)

        assert ledger.total_usd == pytest.approx(3.00)
        assert ledger.cache_read_tokens == 0
