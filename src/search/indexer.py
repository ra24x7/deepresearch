from collections.abc import Callable
from typing import Any

from ingestion.embeddings.base import EmbeddingProvider
from ingestion.enrich.batch import run_batched
from search.indices import (
    build_chunks_mapping,
    build_claims_mapping,
    build_entities_mapping,
    chunks_index_name,
    claims_index_name,
    entities_index_name,
)


def create_indices(client: Any, corpus: str, dimension: int, force: bool = False) -> None:
    specs = [
        (chunks_index_name(corpus), build_chunks_mapping(dimension)),
        (claims_index_name(corpus), build_claims_mapping(dimension)),
        (entities_index_name(corpus), build_entities_mapping()),
    ]
    for name, mapping in specs:
        exists = client.indices.exists(index=name)
        if exists and not force:
            continue
        if exists and force:
            client.indices.delete(index=name)
        client.indices.create(index=name, body=mapping)


def index_chunks(
    client: Any, corpus: str, provider: EmbeddingProvider, chunks: list[dict], on_error: Callable | None = None
) -> tuple[int, int]:
    embeddings = provider.embed_passages([chunk["text"] for chunk in chunks])
    docs = [{**chunk, "embedding": embedding} for chunk, embedding in zip(chunks, embeddings, strict=True)]
    return _bulk_index(client, chunks_index_name(corpus), docs, "chunk_id", on_error)


def index_claims(
    client: Any, corpus: str, provider: EmbeddingProvider, claims: list[dict], on_error: Callable | None = None
) -> tuple[int, int]:
    embeddings = provider.embed_passages([claim["claim_text"] for claim in claims])
    docs = [{**claim, "embedding": embedding} for claim, embedding in zip(claims, embeddings, strict=True)]
    return _bulk_index(client, claims_index_name(corpus), docs, "claim_hash", on_error)


def index_entities(client: Any, corpus: str, entities: list[dict], on_error: Callable | None = None) -> tuple[int, int]:
    return _bulk_index(client, entities_index_name(corpus), entities, "entity_key", on_error)


def _bulk_index(
    client: Any, index_name: str, docs: list[dict], id_field: str, on_error: Callable | None = None
) -> tuple[int, int]:
    def batch_fn(items: list[dict]) -> list[str]:
        response = client.bulk(body=_build_bulk_body(index_name, items, id_field))
        if response.get("errors"):
            raise RuntimeError(f"bulk index into {index_name} reported item-level errors")
        return [item[id_field] for item in items]

    def item_fn(item: dict) -> str:
        response = client.bulk(body=_build_bulk_body(index_name, [item], id_field))
        if response.get("errors"):
            raise RuntimeError(f"failed to index doc {item[id_field]} into {index_name}")
        return item[id_field]

    # Without a reporting hook a failed doc is only ever a count — the caller
    # never learns which one, or why.
    record = on_error or (lambda doc_id, exc: None)
    successes, failures = run_batched(docs, batch_fn, item_fn, lambda item, exc: record(item[id_field], exc))
    return len(successes), len(failures)


def _build_bulk_body(index_name: str, docs: list[dict], id_field: str) -> list[dict]:
    body: list[dict] = []
    for doc in docs:
        body.append({"index": {"_index": index_name, "_id": doc[id_field]}})
        body.append(doc)
    return body
