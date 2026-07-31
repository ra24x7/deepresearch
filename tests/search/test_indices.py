from search.indices import (
    build_chunks_mapping,
    build_claims_mapping,
    build_entities_mapping,
    chunks_index_name,
    claims_index_name,
    entities_index_name,
)


class TestIndexNames:
    def test_chunks_index_name_includes_corpus(self):
        assert chunks_index_name("arxiv2025") == "dr-chunks-arxiv2025"

    def test_claims_index_name_includes_corpus(self):
        assert claims_index_name("arxiv2025") == "dr-claims-arxiv2025"

    def test_entities_index_name_includes_corpus(self):
        assert entities_index_name("arxiv2025") == "dr-entities-arxiv2025"


class TestChunksMapping:
    def test_mapping_carries_given_dimension(self):
        mapping = build_chunks_mapping(1024)

        assert mapping["mappings"]["properties"]["embedding"]["dimension"] == 1024

    def test_mapping_is_dynamic_strict(self):
        mapping = build_chunks_mapping(1024)

        assert mapping["mappings"]["dynamic"] == "strict"

    def test_settings_enable_knn(self):
        mapping = build_chunks_mapping(1024)

        assert mapping["settings"]["index.knn"] is True

    def test_embedding_field_uses_hnsw_faiss_cosine(self):
        mapping = build_chunks_mapping(1024)

        method = mapping["mappings"]["properties"]["embedding"]["method"]
        assert method == {"name": "hnsw", "engine": "faiss", "space_type": "cosinesimil"}

    def test_keyword_and_text_fields_present(self):
        props = build_chunks_mapping(1024)["mappings"]["properties"]

        assert props["chunk_id"] == {"type": "keyword"}
        assert props["arxiv_id"] == {"type": "keyword"}
        assert props["section_title"] == {"type": "keyword"}
        assert props["text"] == {"type": "text"}
        assert props["part_index"] == {"type": "integer"}
        assert props["word_count"] == {"type": "integer"}


class TestClaimsMapping:
    def test_mapping_carries_given_dimension(self):
        mapping = build_claims_mapping(512)

        assert mapping["mappings"]["properties"]["embedding"]["dimension"] == 512

    def test_mapping_is_dynamic_strict(self):
        assert build_claims_mapping(512)["mappings"]["dynamic"] == "strict"

    def test_settings_enable_knn(self):
        assert build_claims_mapping(512)["settings"]["index.knn"] is True

    def test_embedding_field_uses_hnsw_faiss_cosine(self):
        mapping = build_claims_mapping(512)

        method = mapping["mappings"]["properties"]["embedding"]["method"]
        assert method == {"name": "hnsw", "engine": "faiss", "space_type": "cosinesimil"}

    def test_keyword_and_text_fields_present(self):
        props = build_claims_mapping(512)["mappings"]["properties"]

        assert props["claim_hash"] == {"type": "keyword"}
        assert props["arxiv_id"] == {"type": "keyword"}
        assert props["section_title"] == {"type": "keyword"}
        assert props["claim_text"] == {"type": "text"}


class TestEntitiesMapping:
    def test_mapping_is_dynamic_strict(self):
        assert build_entities_mapping()["mappings"]["dynamic"] == "strict"

    def test_has_no_vector_field(self):
        props = build_entities_mapping()["mappings"]["properties"]

        assert "embedding" not in props

    def test_keyword_and_integer_fields_present(self):
        props = build_entities_mapping()["mappings"]["properties"]

        assert props["entity_key"] == {"type": "keyword"}
        assert props["entity_type"] == {"type": "keyword"}
        assert props["surface_forms"] == {"type": "keyword"}
        assert props["link_count"] == {"type": "integer"}
        assert props["linked_arxiv_ids"] == {"type": "keyword"}
        assert props["linked_chunk_ids"] == {"type": "keyword"}
