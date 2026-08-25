from unittest.mock import MagicMock

from llm.bedrock import Usage
from llm.cost import HAIKU_4_5, CostLedger
from obs.tracing import LangfuseTracer, NullTracer, build_tracer


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


class TestLangfuseTracer:
    """The v4 SDK has no `create_generation`; the call this class used to make
    did not exist, so the first run with credentials would have crashed on its
    first question. Nothing exercised it, which is why it survived.
    """

    def test_a_generation_is_recorded_as_a_generation_observation_and_ended(self):
        client, observation = MagicMock(), MagicMock()
        client.start_observation.return_value = observation

        LangfuseTracer(client).generation(
            name="answer:g001", model=HAIKU_4_5, prompt="q", output="a",
            usage=Usage(input_tokens=10, output_tokens=2), cost_usd=0.001,
        )

        kwargs = client.start_observation.call_args.kwargs
        assert kwargs["as_type"] == "generation"
        assert kwargs["name"] == "answer:g001"
        assert kwargs["model"] == HAIKU_4_5
        assert kwargs["input"] == "q"
        assert kwargs["output"] == "a"
        observation.end.assert_called_once()

    def test_token_usage_and_cost_travel_with_the_observation(self):
        client, observation = MagicMock(), MagicMock()
        client.start_observation.return_value = observation

        LangfuseTracer(client).generation(
            name="answer", model=HAIKU_4_5, prompt="q", output="a",
            usage=Usage(input_tokens=10, output_tokens=2, cache_read_tokens=1_500),
            cost_usd=0.25,
        )

        kwargs = client.start_observation.call_args.kwargs
        assert kwargs["usage_details"] == {"input": 10, "output": 2, "cache_read_input_tokens": 1_500}
        # cost comes from CostLedger, never recomputed here (ADR 0006)
        assert kwargs["cost_details"] == {"total": 0.25}

    def test_a_tracing_failure_never_breaks_the_run_it_observes(self):
        # the run is already paid for by the time a trace is written; losing the
        # trace is cheap, losing the answer is not
        client = MagicMock()
        client.start_observation.side_effect = RuntimeError("langfuse is down")

        LangfuseTracer(client).generation(
            name="answer", model=HAIKU_4_5, prompt="q", output="a",
            usage=Usage(input_tokens=1, output_tokens=1), cost_usd=0.0,
        )

    def test_flush_is_forwarded_and_its_failure_is_swallowed(self):
        client = MagicMock()
        LangfuseTracer(client).flush()
        client.flush.assert_called_once()

        client.flush.side_effect = RuntimeError("langfuse is down")
        LangfuseTracer(client).flush()

    def test_it_reports_itself_as_enabled(self):
        assert LangfuseTracer(MagicMock()).enabled is True


class TestFactoryWithCredentials:
    def test_with_both_keys_a_real_tracer_is_built(self, monkeypatch):
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
        monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
        monkeypatch.setattr("langfuse.Langfuse", MagicMock())

        assert isinstance(build_tracer(), LangfuseTracer)

    def test_a_client_that_cannot_be_constructed_falls_back_to_the_no_op(self, monkeypatch):
        # a bad host or an unreachable server must not abort a paid eval run
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
        monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
        monkeypatch.setattr("langfuse.Langfuse", MagicMock(side_effect=RuntimeError("bad host")))

        assert isinstance(build_tracer(), NullTracer)
