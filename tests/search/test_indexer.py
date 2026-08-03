from unittest.mock import MagicMock

from ingestion.embeddings.fake import FakeEmbeddingProvider
from search.indexer import create_indices, index_chunks, index_claims, index_entities
from search.indices import chunks_index_name, claims_index_name, entities_index_name


class TestCreateIndices:
    def test_creates_all_three_indices_when_none_exist(self):
        client = MagicMock()
        client.indices.exists.return_value = False

        create_indices(client, "corpusA", dimension=8)

        created_names = {c.kwargs["index"] for c in client.indices.create.call_args_list}
        assert created_names == {
            chunks_index_name("corpusA"),
            claims_index_name("corpusA"),
            entities_index_name("corpusA"),
        }

    def test_skips_existing_indices_when_force_false(self):
        client = MagicMock()
        client.indices.exists.return_value = True

        create_indices(client, "corpusA", dimension=8, force=False)

        client.indices.create.assert_not_called()
        client.indices.delete.assert_not_called()

    def test_recreates_existing_indices_when_force_true(self):
        client = MagicMock()
        client.indices.exists.return_value = True

        create_indices(client, "corpusA", dimension=8, force=True)

        assert client.indices.delete.call_count == 3
        assert client.indices.create.call_count == 3


def _chunk(chunk_id: str) -> dict:
    return {
        "chunk_id": chunk_id,
        "arxiv_id": "2501.00001",
        "text": f"text for {chunk_id}",
        "section_title": "Introduction",
        "part_index": 0,
        "word_count": 3,
    }


def _claim(claim_hash: str) -> dict:
    return {
        "claim_hash": claim_hash,
        "arxiv_id": "2501.00001",
        "claim_text": f"claim {claim_hash}",
        "section_title": "Introduction",
    }


def _entity(entity_key: str) -> dict:
    return {
        "entity_key": entity_key,
        "entity_type": "model",
        "surface_forms": [entity_key],
        "link_count": 1,
        "linked_arxiv_ids": ["2501.00001"],
        "linked_chunk_ids": ["2501.00001::intro::0"],
    }


class TestIndexChunks:
    def test_embeds_and_bulk_indexes_all_chunks_on_first_try(self):
        client = MagicMock()
        client.bulk.return_value = {"errors": False, "items": []}
        provider = FakeEmbeddingProvider(dimension=8)

        indexed, failed = index_chunks(client, "corpusA", provider, [_chunk("c1"), _chunk("c2")])

        assert (indexed, failed) == (2, 0)
        assert client.bulk.call_count == 1

    def test_embedding_is_attached_to_each_indexed_document(self):
        client = MagicMock()
        client.bulk.return_value = {"errors": False, "items": []}
        provider = FakeEmbeddingProvider(dimension=8)

        index_chunks(client, "corpusA", provider, [_chunk("c1")])

        body = client.bulk.call_args.kwargs["body"]
        assert len(body[1]["embedding"]) == 8

    def test_bulk_document_id_is_deterministic_chunk_id(self):
        client = MagicMock()
        client.bulk.return_value = {"errors": False, "items": []}
        provider = FakeEmbeddingProvider(dimension=8)

        index_chunks(client, "corpusA", provider, [_chunk("c1")])

        action = client.bulk.call_args.kwargs["body"][0]
        assert action["index"]["_id"] == "c1"
        assert action["index"]["_index"] == chunks_index_name("corpusA")

    def test_falls_back_to_per_item_indexing_when_batch_bulk_call_fails(self):
        client = MagicMock()
        client.bulk.side_effect = [
            RuntimeError("connection reset"),
            {"errors": False, "items": []},
            {"errors": False, "items": []},
        ]
        provider = FakeEmbeddingProvider(dimension=8)

        indexed, failed = index_chunks(client, "corpusA", provider, [_chunk("c1"), _chunk("c2")])

        assert (indexed, failed) == (2, 0)
        assert client.bulk.call_count == 3

    def test_item_that_keeps_failing_in_fallback_is_counted_as_failed(self):
        client = MagicMock()
        client.bulk.side_effect = [
            RuntimeError("connection reset"),
            {"errors": False, "items": []},
            RuntimeError("still down"),
        ]
        provider = FakeEmbeddingProvider(dimension=8)

        indexed, failed = index_chunks(client, "corpusA", provider, [_chunk("c1"), _chunk("c2")])

        assert (indexed, failed) == (1, 1)

    def test_batch_response_with_item_level_errors_falls_back_to_per_item(self):
        client = MagicMock()
        client.bulk.side_effect = [
            {"errors": True, "items": []},
            {"errors": False, "items": []},
            {"errors": False, "items": []},
        ]
        provider = FakeEmbeddingProvider(dimension=8)

        indexed, failed = index_chunks(client, "corpusA", provider, [_chunk("c1"), _chunk("c2")])

        assert (indexed, failed) == (2, 0)
        assert client.bulk.call_count == 3

    def test_per_item_response_with_errors_is_counted_as_failed(self):
        client = MagicMock()
        client.bulk.side_effect = [
            {"errors": True, "items": []},
            {"errors": False, "items": []},
            {"errors": True, "items": []},
        ]
        provider = FakeEmbeddingProvider(dimension=8)

        indexed, failed = index_chunks(client, "corpusA", provider, [_chunk("c1"), _chunk("c2")])

        assert (indexed, failed) == (1, 1)


class TestIndexClaims:
    def test_bulk_document_id_is_deterministic_claim_hash(self):
        client = MagicMock()
        client.bulk.return_value = {"errors": False, "items": []}
        provider = FakeEmbeddingProvider(dimension=8)

        index_claims(client, "corpusA", provider, [_claim("hash1")])

        action = client.bulk.call_args.kwargs["body"][0]
        assert action["index"]["_id"] == "hash1"
        assert action["index"]["_index"] == claims_index_name("corpusA")

    def test_counts_correct_on_success(self):
        client = MagicMock()
        client.bulk.return_value = {"errors": False, "items": []}
        provider = FakeEmbeddingProvider(dimension=8)

        indexed, failed = index_claims(client, "corpusA", provider, [_claim("h1"), _claim("h2")])

        assert (indexed, failed) == (2, 0)


class TestIndexEntities:
    def test_indexes_without_embedding_field(self):
        client = MagicMock()
        client.bulk.return_value = {"errors": False, "items": []}

        indexed, failed = index_entities(client, "corpusA", [_entity("model-x")])

        assert (indexed, failed) == (1, 0)
        body = client.bulk.call_args.kwargs["body"]
        assert "embedding" not in body[1]

    def test_bulk_document_id_is_deterministic_entity_key(self):
        client = MagicMock()
        client.bulk.return_value = {"errors": False, "items": []}

        index_entities(client, "corpusA", [_entity("model-x")])

        action = client.bulk.call_args.kwargs["body"][0]
        assert action["index"]["_id"] == "model-x"
        assert action["index"]["_index"] == entities_index_name("corpusA")


class TestFailureReporting:
    def test_on_error_receives_failed_doc_id_and_exception(self):
        client = MagicMock()
        client.bulk.side_effect = RuntimeError("mapping rejected")
        seen = []

        indexed, failed = index_entities(client, "corpusA", [_entity("model-x")], on_error=lambda i, e: seen.append((i, str(e))))

        assert (indexed, failed) == (0, 1)
        assert seen[0][0] == "model-x"
        assert "mapping rejected" in seen[0][1]
