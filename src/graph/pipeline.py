"""The Phase 4 read path: guardrail -> route -> retrieve -> generate,
with grade-and-rewrite as an escape hatch off the retrieve step and a metadata
short-circuit off the `computable` route.

Retrieval and generation arrive as injected callables rather than clients, so
the graph is exercised end to end in tests without OpenSearch, Bedrock, or a
single paid call. `scripts/` wires the real ones in.
"""

from collections.abc import Callable, Collection, Sequence
from typing import NamedTuple, TypedDict

from langgraph.graph import END, StateGraph

from generation.answer import GeneratedAnswer
from generation.escape_hatch import RetrievalGrade, RewrittenQuestion
from generation.prompts import ABSTENTION_SENTINEL
from llm.cost import CostLedger
from retrieval.router import route as route_query
from retrieval.schemas import FusedHit, Route

SearchFn = Callable[[str], Sequence[FusedHit]]
GenerateFn = Callable[[str, Sequence[FusedHit]], GeneratedAnswer]
# Returns an answer text when a corpus aggregate covers the question, else
# None. Typed as a plain string so the graph never imports the tool layer.
MetadataFn = Callable[[str], str | None]
GradeFn = Callable[[str, Sequence[FusedHit]], RetrievalGrade]
RewriteFn = Callable[[str, Sequence[FusedHit]], RewrittenQuestion]


class EscapeHatch(NamedTuple):
    """Grade-and-rewrite, and the confidence below which it fires.

    `threshold` is compared against the reranker's own relevance score for its
    top hit, so it is only meaningful under a calibrated cross-encoder --
    `IdentityReranker` returns RRF scores, which live on a different scale.
    Build the pipeline without a hatch to disable the path entirely.
    """

    grade: GradeFn
    rewrite: RewriteFn
    threshold: float
    model_id: str


class QueryState(TypedDict, total=False):
    question: str
    retrieval_question: str
    route: Route | None
    from_metadata: bool
    hits: tuple[FusedHit, ...]
    confidence: float
    graded: bool
    grade_sufficient: bool
    grade_reason: str
    rewritten: bool
    answer: str | None
    abstained: bool
    ledger: CostLedger


def initial_state(question: str) -> QueryState:
    return QueryState(
        question=question,
        retrieval_question=question,
        route=None,
        from_metadata=False,
        hits=(),
        confidence=0.0,
        graded=False,
        grade_sufficient=True,
        grade_reason="",
        rewritten=False,
        answer=None,
        abstained=False,
        ledger=CostLedger(),
    )


def build_pipeline(
    search: SearchFn,
    generate: GenerateFn,
    model_id: str,
    vocabulary: Collection[str] = frozenset(),
    escape_hatch: EscapeHatch | None = None,
    metadata: MetadataFn | None = None,
):
    graph = StateGraph(QueryState)
    graph.add_node("guardrail", _guardrail_node(vocabulary))
    graph.add_node("retrieve", _retrieve_node(search))
    graph.add_node("generate", _generate_node(generate, model_id))

    graph.set_entry_point("guardrail")
    graph.add_edge("generate", END)

    if metadata is None:
        graph.add_conditional_edges(
            "guardrail", _after_guardrail(has_metadata=False), {"retrieve": "retrieve", END: END}
        )
    else:
        graph.add_node("metadata", _metadata_node(metadata))
        graph.add_conditional_edges(
            "guardrail",
            _after_guardrail(has_metadata=True),
            {"metadata": "metadata", "retrieve": "retrieve", END: END},
        )
        graph.add_conditional_edges(
            "metadata", _after_metadata, {"retrieve": "retrieve", END: END}
        )

    if escape_hatch is None:
        graph.add_edge("retrieve", "generate")
        return graph.compile()

    graph.add_node("grade", _grade_node(escape_hatch))
    graph.add_node("rewrite", _rewrite_node(escape_hatch))
    graph.add_conditional_edges(
        "retrieve", _after_retrieve(escape_hatch), {"grade": "grade", "generate": "generate"}
    )
    graph.add_conditional_edges("grade", _after_grade, {"rewrite": "rewrite", "generate": "generate"})
    graph.add_edge("rewrite", "retrieve")
    return graph.compile()


def _guardrail_node(vocabulary: Collection[str]) -> Callable[[QueryState], QueryState]:
    def node(state: QueryState) -> QueryState:
        route = route_query(state["question"], vocabulary)
        if route != "out_of_domain":
            return QueryState(route=route)
        # Refusing here is what makes an out-of-domain question free. The sentence
        # matches the generator's, so the judge grades both by rubric rule 4.
        return QueryState(route=route, answer=ABSTENTION_SENTINEL, abstained=True)

    return node


def _after_guardrail(has_metadata: bool) -> Callable[[QueryState], str]:
    def decide(state: QueryState) -> str:
        if state["route"] == "out_of_domain":
            return END
        # Only a corpus aggregate is worth a metadata lookup; everything else is
        # in the chunks (tools/supervisor.py, dispatch).
        return "metadata" if has_metadata and state["route"] == "computable" else "retrieve"

    return decide


def _metadata_node(metadata: MetadataFn) -> Callable[[QueryState], QueryState]:
    def node(state: QueryState) -> QueryState:
        answer = metadata(state["question"])
        if answer is None:
            return QueryState(from_metadata=False)
        # No retrieval, no generation, no judge context: the answer is a fact
        # about the corpus, and reading it costs nothing.
        return QueryState(from_metadata=True, answer=answer)

    return node


def _after_metadata(state: QueryState) -> str:
    return END if state["from_metadata"] else "retrieve"


def _retrieve_node(search: SearchFn) -> Callable[[QueryState], QueryState]:
    def node(state: QueryState) -> QueryState:
        hits = tuple(search(state["retrieval_question"]))
        return QueryState(hits=hits, confidence=hits[0].score if hits else 0.0)

    return node


def _after_retrieve(hatch: EscapeHatch) -> Callable[[QueryState], str]:
    def decide(state: QueryState) -> str:
        # One grade, one rewrite, one extra retrieval: the second pass skips the
        # gate, which is what makes the hatch terminate.
        if state["rewritten"] or state["confidence"] >= hatch.threshold:
            return "generate"
        return "grade"

    return decide


def _grade_node(hatch: EscapeHatch) -> Callable[[QueryState], QueryState]:
    def node(state: QueryState) -> QueryState:
        grade = hatch.grade(state["retrieval_question"], state["hits"])
        return QueryState(
            graded=True,
            grade_sufficient=grade.sufficient,
            grade_reason=grade.reason,
            ledger=state["ledger"].add(grade.usage, hatch.model_id),
        )

    return node


def _after_grade(state: QueryState) -> str:
    return "generate" if state["grade_sufficient"] else "rewrite"


def _rewrite_node(hatch: EscapeHatch) -> Callable[[QueryState], QueryState]:
    def node(state: QueryState) -> QueryState:
        result = hatch.rewrite(state["question"], state["hits"])
        return QueryState(
            retrieval_question=result.question,
            rewritten=True,
            ledger=state["ledger"].add(result.usage, hatch.model_id),
        )

    return node


def _generate_node(generate: GenerateFn, model_id: str) -> Callable[[QueryState], QueryState]:
    def node(state: QueryState) -> QueryState:
        # The rewrite is a retrieval device; the question asked is what gets answered.
        result = generate(state["question"], state["hits"])
        return QueryState(
            answer=result.text,
            abstained=result.abstained,
            ledger=state["ledger"].add(result.usage, model_id),
        )

    return node
