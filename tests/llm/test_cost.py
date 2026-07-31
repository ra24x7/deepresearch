import pytest

from llm.bedrock import Usage
from llm.cost import CostLedger


class TestCostLedger:
    def test_starts_at_zero_tokens_and_cost(self):
        ledger = CostLedger()

        assert ledger.input_tokens == 0
        assert ledger.output_tokens == 0
        assert ledger.total_usd == 0.0

    def test_add_returns_a_new_ledger_with_accumulated_tokens(self):
        ledger = CostLedger()

        updated = ledger.add(Usage(input_tokens=100, output_tokens=50))

        assert updated.input_tokens == 100
        assert updated.output_tokens == 50
        assert ledger.input_tokens == 0
        assert ledger.output_tokens == 0

    def test_add_accumulates_across_multiple_calls(self):
        ledger = CostLedger()

        updated = ledger.add(Usage(input_tokens=100, output_tokens=50)).add(Usage(input_tokens=200, output_tokens=30))

        assert updated.input_tokens == 300
        assert updated.output_tokens == 80

    def test_total_usd_uses_haiku_price_table(self):
        ledger = CostLedger(input_tokens=1_000_000, output_tokens=1_000_000)

        assert ledger.total_usd == pytest.approx(1.00 + 5.00)

    def test_per_paper_usd_divides_total_by_paper_count(self):
        ledger = CostLedger(input_tokens=1_000_000, output_tokens=0)

        assert ledger.per_paper_usd(4) == pytest.approx(0.25)

    def test_per_paper_usd_raises_on_zero_papers(self):
        ledger = CostLedger(input_tokens=1_000_000, output_tokens=0)

        with pytest.raises(ValueError, match="n_papers"):
            ledger.per_paper_usd(0)

    def test_ledger_is_frozen(self):
        ledger = CostLedger()

        with pytest.raises(ValueError):
            ledger.input_tokens = 5
