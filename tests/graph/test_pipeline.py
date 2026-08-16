from config import GenerationSettings
from generation.answer import GeneratedAnswer
from generation.prompts import ABSTENTION_SENTINEL
from graph.pipeline import build_pipeline, initial_state
from llm.bedrock import Usage
from llm.cost import HAIKU_4_5
from retrieval.schemas import FusedHit

MODEL_ID = GenerationSettings().model_id


def _hit(text: str = "passage") -> FusedHit:
    return FusedHit(
        doc_id="2607.27136::0", arxiv_id="2607.27136", score=1.0, text=text, channels=("bm25",)
    )


def _recording_search(hits: list[FusedHit], calls: list[str]):
    def search(question: str):
        calls.append(question)
        return tuple(hits)

    return search


def _recording_generate(answer: GeneratedAnswer, seen: list[tuple], calls: list[str] | None = None):
    def generate(question: str, hits):
        seen.append((question, tuple(hits)))
        if calls is not None:
            calls.append(question)
        return answer

    return generate


def _answer(text: str = "the answer", abstained: bool = False) -> GeneratedAnswer:
    return GeneratedAnswer(text=text, usage=Usage(input_tokens=1_000_000, output_tokens=0), abstained=abstained)


class TestGuardrail:
    def test_an_out_of_domain_question_never_reaches_retrieval_or_generation(self):
        # the whole point of the rule-based guardrail: an out-of-domain
        # question must cost nothing, so neither paid stage may run
        searched: list[str] = []
        generated: list[str] = []
        pipeline = build_pipeline(
            search=_recording_search([_hit()], searched),
            generate=_recording_generate(_answer(), [], generated),
            model_id=MODEL_ID,
        )

        final = pipeline.invoke(initial_state("what is the weather today?"))

        assert final["route"] == "out_of_domain"
        assert searched == []
        assert generated == []

    def test_an_out_of_domain_question_is_answered_with_the_abstention_sentence(self):
        pipeline = build_pipeline(
            search=_recording_search([], []), generate=_recording_generate(_answer(), []), model_id=MODEL_ID
        )

        final = pipeline.invoke(initial_state("tell me a joke"))

        assert final["answer"] == ABSTENTION_SENTINEL
        assert final["abstained"] is True

    def test_an_out_of_domain_question_costs_nothing(self):
        pipeline = build_pipeline(
            search=_recording_search([], []), generate=_recording_generate(_answer(), []), model_id=MODEL_ID
        )

        final = pipeline.invoke(initial_state("what is the weather today?"))

        assert final["ledger"].total_usd == 0.0


class TestHappyPath:
    def test_a_research_question_flows_through_retrieval_into_generation(self):
        searched: list[str] = []
        seen: list[tuple] = []
        pipeline = build_pipeline(
            search=_recording_search([_hit("existing retrievers rank triplets")], searched),
            generate=_recording_generate(_answer("KAMR faults ranking."), seen),
            model_id=MODEL_ID,
        )

        final = pipeline.invoke(initial_state("what does KAMR identify as the failing?"))

        assert searched == ["what does KAMR identify as the failing?"]
        assert final["answer"] == "KAMR faults ranking."

    def test_the_retrieved_passages_reach_the_generator(self):
        seen: list[tuple] = []
        hit = _hit("existing retrievers rank triplets")
        pipeline = build_pipeline(
            search=_recording_search([hit], []),
            generate=_recording_generate(_answer(), seen),
            model_id=MODEL_ID,
        )

        pipeline.invoke(initial_state("how does retrieval fail?"))

        assert seen[0][1] == (hit,)

    def test_the_route_is_recorded_on_the_final_state(self):
        pipeline = build_pipeline(
            search=_recording_search([], []), generate=_recording_generate(_answer(), []), model_id=MODEL_ID
        )

        final = pipeline.invoke(initial_state("how does the chunker work?"))

        assert final["route"] == "semantic"


class TestCost:
    def test_generation_usage_lands_in_the_ledger_under_the_generation_model(self):
        pipeline = build_pipeline(
            search=_recording_search([_hit()], []),
            generate=_recording_generate(_answer(), []),
            model_id=HAIKU_4_5,
        )

        final = pipeline.invoke(initial_state("how does the chunker work?"))

        assert final["ledger"].total_usd == 1.00
        assert final["ledger"].input_tokens == 1_000_000


class TestAbstention:
    def test_a_model_abstention_is_carried_onto_the_state(self):
        pipeline = build_pipeline(
            search=_recording_search([_hit()], []),
            generate=_recording_generate(_answer(ABSTENTION_SENTINEL, abstained=True), []),
            model_id=MODEL_ID,
        )

        final = pipeline.invoke(initial_state("what is the unstated limitation?"))

        assert final["abstained"] is True
