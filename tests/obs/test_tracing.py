from llm.bedrock import Usage
from llm.cost import HAIKU_4_5, CostLedger
from obs.tracing import NullTracer, build_tracer


class TestNullTracer:
    def test_recording_a_generation_does_nothing_and_raises_nothing(self):
        tracer = NullTracer()

        tracer.generation(
            name="answer",
            model=HAIKU_4_5,
            prompt="q",
            output="a",
            usage=Usage(input_tokens=10, output_tokens=2),
            cost_usd=0.001,
        )
        tracer.flush()

    def test_it_reports_itself_as_disabled(self):
        assert NullTracer().enabled is False


class TestFactory:
    def test_without_credentials_the_tracer_is_the_no_op(self, monkeypatch):
        # tests and offline eval runs must never need Langfuse credentials —
        # same rule the identity reranker and fake embedding provider follow
        monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
        monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

        assert isinstance(build_tracer(), NullTracer)

    def test_a_half_configured_environment_still_falls_back_to_the_no_op(self, monkeypatch):
        # one key without the other is a misconfiguration; failing closed beats
        # crashing an eval run partway through a paid batch
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-only")
        monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

        assert isinstance(build_tracer(), NullTracer)


class TestLedgerIntegration:
    def test_a_ledger_total_can_be_passed_straight_through_as_cost(self):
        ledger = CostLedger().add(Usage(input_tokens=1_000_000, output_tokens=0), HAIKU_4_5)
        tracer = NullTracer()

        tracer.generation(
            name="answer",
            model=HAIKU_4_5,
            prompt="q",
            output="a",
            usage=Usage(input_tokens=1_000_000, output_tokens=0),
            cost_usd=ledger.total_usd,
        )

        assert ledger.total_usd == 1.00
