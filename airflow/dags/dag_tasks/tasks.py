"""Airflow task callables — thin wrappers over tested functions in src/pipeline.

No business logic here: each task resolves services, calls one pipeline stage,
and hands its stats onward via XCom.
"""

from dag_tasks.common import (
    PAPERS_DIR,
    embedding_provider,
    llm_invoke_json,
    pipeline_settings,
    search_client,
    session_factory,
)
from ingestion.arxiv_client import fetch_by_query
from ingestion.ids import validate_arxiv_id
from pipeline.stages import (
    embed_and_index_paper,
    enrich_paper,
    index_entities_for_corpus,
    parse_and_chunk_paper,
)
from search.indexer import create_indices


def resolve_arxiv_ids(**context) -> list[str]:
    """Explicit ids win; otherwise query arXiv by category and date window."""
    params = context["params"]
    if params.get("arxiv_ids"):
        # DAG params are operator input: reject a malformed id here rather than
        # let it fan out into per-paper tasks that each build a path from it.
        return [validate_arxiv_id(arxiv_id) for arxiv_id in params["arxiv_ids"]]

    metadata = fetch_by_query(
        params["category"],
        params["from_date"],
        params["to_date"],
        params["max_results"],
        pipeline_settings().arxiv,
    )
    return [m.arxiv_id for m in metadata]


def setup_indices(**context) -> None:
    create_indices(search_client(), context["params"]["corpus"], embedding_provider().dimension)


def parse_and_chunk(arxiv_id: str, **context) -> dict:
    with session_factory()() as session:
        return parse_and_chunk_paper(arxiv_id, context["params"]["corpus"], PAPERS_DIR, session, pipeline_settings())


def enrich(arxiv_id: str, **context) -> dict:
    with session_factory()() as session:
        return enrich_paper(arxiv_id, session, llm_invoke_json, pipeline_settings())


def embed_and_index(arxiv_id: str, **context) -> dict:
    with session_factory()() as session:
        return embed_and_index_paper(
            arxiv_id,
            context["params"]["corpus"],
            session,
            search_client(),
            embedding_provider(),
            pipeline_settings(),
        )


def index_entities(**context) -> dict:
    with session_factory()() as session:
        return index_entities_for_corpus(context["params"]["corpus"], session, search_client())
