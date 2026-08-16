"""The Phase 4 happy path: guardrail -> route -> retrieve -> generate.

Retrieval and generation arrive as injected callables rather than clients, so
the graph is exercised end to end in tests without OpenSearch, Bedrock, or a
single paid call. `scripts/` wires the real ones in.
"""

from collections.abc import Callable, Sequence
from typing import TypedDict

from langgraph.graph import END, StateGraph

from generation.answer import GeneratedAnswer
from generation.prompts import ABSTENTION_SENTINEL
from llm.cost import CostLedger
from retrieval.router import route as route_query
from retrieval.schemas import FusedHit, Route

SearchFn = Callable[[str], Sequence[FusedHit]]
GenerateFn = Callable[[str, Sequence[FusedHit]], GeneratedAnswer]


class QueryState(TypedDict, total=False):
    question: str
    route: Route | None
    hits: tuple[FusedHit, ...]
    answer: str | None
    abstained: bool
    ledger: CostLedger


def initial_state(question: str) -> QueryState:
    return QueryState(
        question=question, route=None, hits=(), answer=None, abstained=False, ledger=CostLedger()
    )


def build_pipeline(search: SearchFn, generate: GenerateFn, model_id: str):
    graph = StateGraph(QueryState)
    graph.add_node("guardrail", _guardrail_node)
    graph.add_node("retrieve", _retrieve_node(search))
    graph.add_node("generate", _generate_node(generate, model_id))

    graph.set_entry_point("guardrail")
    graph.add_conditional_edges("guardrail", _after_guardrail, {"retrieve": "retrieve", END: END})
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", END)
    return graph.compile()


def _guardrail_node(state: QueryState) -> QueryState:
    route = route_query(state["question"])
    if route != "out_of_domain":
        return QueryState(route=route)
    # Refusing here is what makes an out-of-domain question free. The sentence
    # matches the generator's, so the judge grades both by rubric rule 4.
    return QueryState(route=route, answer=ABSTENTION_SENTINEL, abstained=True)


def _after_guardrail(state: QueryState) -> str:
    return END if state["route"] == "out_of_domain" else "retrieve"


def _retrieve_node(search: SearchFn) -> Callable[[QueryState], QueryState]:
    def node(state: QueryState) -> QueryState:
        return QueryState(hits=tuple(search(state["question"])))

    return node


def _generate_node(generate: GenerateFn, model_id: str) -> Callable[[QueryState], QueryState]:
    def node(state: QueryState) -> QueryState:
        result = generate(state["question"], state["hits"])
        return QueryState(
            answer=result.text,
            abstained=result.abstained,
            ledger=state["ledger"].add(result.usage, model_id),
        )

    return node
