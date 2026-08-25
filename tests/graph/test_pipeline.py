from config import GenerationSettings
from generation.answer import GeneratedAnswer
from generation.escape_hatch import RetrievalGrade, RewrittenQuestion
from generation.prompts import ABSTENTION_SENTINEL
from graph.pipeline import EscapeHatch, build_pipeline, initial_state
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


def _hit_scored(score: float) -> FusedHit:
    return FusedHit(
        doc_id="2607.27136::0", arxiv_id="2607.27136", score=score, text="passage", channels=("bm25",)
    )


_HATCH_USAGE = Usage(input_tokens=500, output_tokens=10)


def _hatch(
    threshold: float,
    sufficient: bool = True,
    rewrite_to: str = "a rewritten question?",
    graded: list[str] | None = None,
    rewritten: list[str] | None = None,
    hatch_model: str = MODEL_ID,
) -> EscapeHatch:
    def grade(question: str, hits):
        if graded is not None:
            graded.append(question)
        return RetrievalGrade(sufficient=sufficient, reason="", usage=_HATCH_USAGE)

    def rewrite(question: str, hits):
        if rewritten is not None:
            rewritten.append(question)
        return RewrittenQuestion(question=rewrite_to, usage=_HATCH_USAGE)

    return EscapeHatch(grade=grade, rewrite=rewrite, threshold=threshold, model_id=hatch_model)


class TestTheGuardrailRoutesWithTheEntityVocabulary:
    def test_an_acronym_the_index_knows_routes_entity_anchored(self):
        pipeline = build_pipeline(
            search=_recording_search([_hit()], []),
            generate=_recording_generate(_answer(), []),
            model_id=MODEL_ID,
            vocabulary=frozenset({"a-rag"}),
        )

        final = pipeline.invoke(initial_state("What tools does A-RAG provide?"))

        assert final["route"] == "entity_anchored"

    def test_without_a_vocabulary_the_same_question_is_semantic(self):
        pipeline = build_pipeline(
            search=_recording_search([_hit()], []),
            generate=_recording_generate(_answer(), []),
            model_id=MODEL_ID,
        )

        final = pipeline.invoke(initial_state("What tools does A-RAG provide?"))

        assert final["route"] == "semantic"


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


class TestTheEscapeHatch:
    """Grade-and-rewrite fires only when the reranker is unsure of its top hit.

    The gate is the reranker's own relevance score, so a threshold is only
    meaningful under a calibrated cross-encoder. `IdentityReranker` emits RRF
    scores on a different scale entirely -- passing no hatch disables the whole
    path, which is what an identity run must do.
    """

    def test_a_confident_retrieval_never_pays_to_grade(self):
        graded: list[str] = []
        pipeline = build_pipeline(
            search=_recording_search([_hit_scored(0.91)], []),
            generate=_recording_generate(_answer(), []),
            model_id=MODEL_ID,
            escape_hatch=_hatch(threshold=0.3, graded=graded),
        )

        final = pipeline.invoke(initial_state("a confident question?"))

        assert graded == []
        assert final["graded"] is False
        assert final["rewritten"] is False

    def test_a_low_confidence_retrieval_is_graded(self):
        graded: list[str] = []
        pipeline = build_pipeline(
            search=_recording_search([_hit_scored(0.02)], []),
            generate=_recording_generate(_answer(), []),
            model_id=MODEL_ID,
            escape_hatch=_hatch(threshold=0.3, graded=graded),
        )

        final = pipeline.invoke(initial_state("a doubtful question?"))

        assert graded == ["a doubtful question?"]
        assert final["graded"] is True

    def test_a_sufficient_grade_generates_without_rewriting(self):
        rewritten: list[str] = []
        pipeline = build_pipeline(
            search=_recording_search([_hit_scored(0.02)], []),
            generate=_recording_generate(_answer(), []),
            model_id=MODEL_ID,
            escape_hatch=_hatch(threshold=0.3, sufficient=True, rewritten=rewritten),
        )

        final = pipeline.invoke(initial_state("a doubtful question?"))

        assert rewritten == []
        assert final["rewritten"] is False

    def test_an_insufficient_grade_rewrites_and_retrieves_again(self):
        searched: list[str] = []
        pipeline = build_pipeline(
            search=_recording_search([_hit_scored(0.02)], searched),
            generate=_recording_generate(_answer(), []),
            model_id=MODEL_ID,
            escape_hatch=_hatch(threshold=0.3, sufficient=False, rewrite_to="a better question?"),
        )

        final = pipeline.invoke(initial_state("a doubtful question?"))

        assert searched == ["a doubtful question?", "a better question?"]
        assert final["rewritten"] is True

    def test_the_rewritten_question_is_never_graded_a_second_time(self):
        # The hatch must terminate: one grade, one rewrite, one extra retrieval.
        graded: list[str] = []
        pipeline = build_pipeline(
            search=_recording_search([_hit_scored(0.02)], []),
            generate=_recording_generate(_answer(), []),
            model_id=MODEL_ID,
            escape_hatch=_hatch(threshold=0.3, sufficient=False, graded=graded),
        )

        pipeline.invoke(initial_state("a doubtful question?"))

        assert len(graded) == 1

    def test_the_answer_is_generated_from_the_original_question(self):
        # Rewriting is a retrieval device. Answering the rewrite instead of what
        # was asked would change what the judge is grading.
        seen: list[tuple] = []
        pipeline = build_pipeline(
            search=_recording_search([_hit_scored(0.02)], []),
            generate=_recording_generate(_answer(), seen),
            model_id=MODEL_ID,
            escape_hatch=_hatch(threshold=0.3, sufficient=False, rewrite_to="a better question?"),
        )

        pipeline.invoke(initial_state("a doubtful question?"))

        assert seen[-1][0] == "a doubtful question?"

    def test_without_a_hatch_a_low_confidence_retrieval_goes_straight_to_generation(self):
        pipeline = build_pipeline(
            search=_recording_search([_hit_scored(0.02)], []),
            generate=_recording_generate(_answer(), []),
            model_id=MODEL_ID,
        )

        final = pipeline.invoke(initial_state("a doubtful question?"))

        assert final["graded"] is False
        assert final["answer"] == "the answer"

    def test_an_empty_retrieval_has_zero_confidence_and_is_graded(self):
        graded: list[str] = []
        pipeline = build_pipeline(
            search=_recording_search([], []),
            generate=_recording_generate(_answer(), []),
            model_id=MODEL_ID,
            escape_hatch=_hatch(threshold=0.3, graded=graded),
        )

        final = pipeline.invoke(initial_state("a question nothing matches?"))

        assert final["confidence"] == 0.0
        assert graded == ["a question nothing matches?"]

    def test_confidence_is_the_top_hit_score(self):
        pipeline = build_pipeline(
            search=_recording_search([_hit_scored(0.77), _hit_scored(0.11)], []),
            generate=_recording_generate(_answer(), []),
            model_id=MODEL_ID,
            escape_hatch=_hatch(threshold=0.3),
        )

        final = pipeline.invoke(initial_state("a confident question?"))

        assert final["confidence"] == 0.77

    def test_grade_and_rewrite_tokens_are_billed_to_the_hatch_model(self):
        pipeline = build_pipeline(
            search=_recording_search([_hit_scored(0.02)], []),
            generate=_recording_generate(_answer(), []),
            model_id=MODEL_ID,
            escape_hatch=_hatch(threshold=0.3, sufficient=False, hatch_model=HAIKU_4_5),
        )

        final = pipeline.invoke(initial_state("a doubtful question?"))

        # 500 in / 10 out for the grade, the same again for the rewrite
        assert final["ledger"].tokens_by_model[HAIKU_4_5].input_tokens == 1_000_000 + 1_000
        assert final["ledger"].tokens_by_model[HAIKU_4_5].output_tokens == 20

    def test_an_out_of_domain_question_never_reaches_the_hatch(self):
        graded: list[str] = []
        pipeline = build_pipeline(
            search=_recording_search([], []),
            generate=_recording_generate(_answer(), []),
            model_id=MODEL_ID,
            escape_hatch=_hatch(threshold=0.3, graded=graded),
        )

        final = pipeline.invoke(initial_state("what is the weather today?"))

        assert final["route"] == "out_of_domain"
        assert graded == []


class TestTheMetadataRoute:
    """A corpus aggregate is in Postgres, not in any chunk. Answering it from
    metadata skips retrieval and generation entirely -- and costs nothing.

    Measured on the golden set: the rule fires on exactly g020 and g038, the
    two `computable` questions A2 got wrong that a metadata query can fix, and
    on no others.
    """

    def test_a_computable_question_answered_from_metadata_skips_retrieval(self):
        searched: list[str] = []
        generated: list[str] = []
        pipeline = build_pipeline(
            search=_recording_search([_hit()], searched),
            generate=_recording_generate(_answer(), [], generated),
            model_id=MODEL_ID,
            metadata=lambda question: "The corpus holds 54 papers.",
        )

        final = pipeline.invoke(initial_state("How many papers in the corpus were published in 2026?"))

        assert final["answer"] == "The corpus holds 54 papers."
        assert final["from_metadata"] is True
        assert searched == []
        assert generated == []

    def test_answering_from_metadata_costs_nothing(self):
        pipeline = build_pipeline(
            search=_recording_search([_hit()], []),
            generate=_recording_generate(_answer(), []),
            model_id=MODEL_ID,
            metadata=lambda question: "The corpus holds 54 papers.",
        )

        final = pipeline.invoke(initial_state("How many papers are in the corpus?"))

        assert final["ledger"].total_usd == 0.0

    def test_a_computable_question_no_rule_matches_falls_through_to_retrieval(self):
        searched: list[str] = []
        pipeline = build_pipeline(
            search=_recording_search([_hit()], searched),
            generate=_recording_generate(_answer(), []),
            model_id=MODEL_ID,
            metadata=lambda question: None,
        )

        question = "How many papers in the corpus mention retrieval augmentation?"
        final = pipeline.invoke(initial_state(question))

        assert final["route"] == "computable"
        assert final["from_metadata"] is False
        assert searched == [question]

    def test_a_semantic_question_never_reaches_the_metadata_tool(self):
        asked: list[str] = []

        def metadata(question: str):
            asked.append(question)
            return "should not be used"

        pipeline = build_pipeline(
            search=_recording_search([_hit()], []),
            generate=_recording_generate(_answer(), []),
            model_id=MODEL_ID,
            metadata=metadata,
        )

        final = pipeline.invoke(initial_state("Why does interleaving reasoning with search help?"))

        assert asked == []
        assert final["from_metadata"] is False

    def test_without_a_metadata_tool_a_computable_question_retrieves_as_before(self):
        searched: list[str] = []
        pipeline = build_pipeline(
            search=_recording_search([_hit()], searched),
            generate=_recording_generate(_answer(), []),
            model_id=MODEL_ID,
        )

        question = "How many papers in the corpus were published in 2026?"
        pipeline.invoke(initial_state(question))

        assert searched == [question]

    def test_an_out_of_domain_question_still_short_circuits_ahead_of_metadata(self):
        asked: list[str] = []
        pipeline = build_pipeline(
            search=_recording_search([], []),
            generate=_recording_generate(_answer(), []),
            model_id=MODEL_ID,
            metadata=lambda question: asked.append(question) or "x",
        )

        final = pipeline.invoke(initial_state("what is the weather today?"))

        assert final["route"] == "out_of_domain"
        assert asked == []
