from retrieval.vocabulary import build_entity_vocabulary


class TestBuildEntityVocabulary:
    def test_keys_and_surface_forms_both_become_anchors(self):
        vocabulary = build_entity_vocabulary([("a-rag", ["A-RAG", "Agentic RAG"])])

        assert vocabulary == frozenset({"a-rag", "agentic rag"})

    def test_surface_forms_are_normalised(self):
        vocabulary = build_entity_vocabulary([("bge-m3", ["BGE-M3", "  bge‐m3  "])])

        assert vocabulary == frozenset({"bge-m3"})

    def test_an_entity_with_no_surface_forms_still_contributes_its_key(self):
        assert build_entity_vocabulary([("trek", [])]) == frozenset({"trek"})

    def test_blank_surface_forms_are_dropped(self):
        assert build_entity_vocabulary([("trek", ["", "   "])]) == frozenset({"trek"})

    def test_an_empty_table_yields_an_empty_vocabulary(self):
        assert build_entity_vocabulary([]) == frozenset()
