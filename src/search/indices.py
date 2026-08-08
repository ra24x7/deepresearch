from ingestion.ids import validate_corpus

_INDEX_PREFIX = "dr"
_KNN_METHOD = {"name": "hnsw", "engine": "faiss", "space_type": "cosinesimil"}


# The corpus name reaches OpenSearch as part of a URL path, where `*` and `..`
# would widen a read — or a delete — beyond the intended index.
def chunks_index_name(corpus: str) -> str:
    return f"{_INDEX_PREFIX}-chunks-{validate_corpus(corpus)}"


def claims_index_name(corpus: str) -> str:
    return f"{_INDEX_PREFIX}-claims-{validate_corpus(corpus)}"


def entities_index_name(corpus: str) -> str:
    return f"{_INDEX_PREFIX}-entities-{validate_corpus(corpus)}"


def _knn_vector_field(dimension: int) -> dict:
    return {"type": "knn_vector", "dimension": dimension, "method": _KNN_METHOD}


def build_chunks_mapping(dimension: int) -> dict:
    return {
        "settings": {"index.knn": True},
        "mappings": {
            "dynamic": "strict",
            "properties": {
                "chunk_id": {"type": "keyword"},
                "arxiv_id": {"type": "keyword"},
                "section_title": {"type": "keyword"},
                "text": {"type": "text"},
                "part_index": {"type": "integer"},
                "word_count": {"type": "integer"},
                "page_start": {"type": "integer"},
                "page_end": {"type": "integer"},
                "embedding": _knn_vector_field(dimension),
            },
        },
    }


def build_claims_mapping(dimension: int) -> dict:
    return {
        "settings": {"index.knn": True},
        "mappings": {
            "dynamic": "strict",
            "properties": {
                "claim_hash": {"type": "keyword"},
                "arxiv_id": {"type": "keyword"},
                "section_title": {"type": "keyword"},
                "claim_text": {"type": "text"},
                "embedding": _knn_vector_field(dimension),
            },
        },
    }


def build_entities_mapping() -> dict:
    return {
        "mappings": {
            "dynamic": "strict",
            "properties": {
                "entity_key": {"type": "keyword"},
                "entity_type": {"type": "keyword"},
                "surface_forms": {"type": "keyword"},
                "link_count": {"type": "integer"},
                "linked_arxiv_ids": {"type": "keyword"},
                "linked_chunk_ids": {"type": "keyword"},
            },
        },
    }
