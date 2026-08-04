import pytest

from retrieval.router import route


class TestComputableRoute:
    @pytest.mark.parametrize(
        "query",
        [
            "How many papers in the corpus were published in 2026?",
            "Which papers were published in 2025?",
            "What is the average number of authors per paper?",
            "How many documents mention retrieval augmentation?",
        ],
    )
    def test_aggregate_questions_over_the_corpus_route_to_computable(self, query):
        assert route(query) == "computable"

    @pytest.mark.parametrize(
        "query",
        [
            "How many training samples does the EvoTrain dataset contain?",
            "How many questions does the evaluation benchmark contain?",
        ],
    )
    def test_counting_inside_a_single_paper_is_not_computable(self, query):
        assert route(query) != "computable"


class TestEntityAnchoredRoute:
    @pytest.mark.parametrize("query", ["What does 2510.12345 propose?", "Summarise arXiv 2401.09876 for me."])
    def test_arxiv_ids_anchor_the_query(self, query):
        assert route(query) == "entity_anchored"

    @pytest.mark.parametrize(
        "query",
        [
            "Which method reports the highest Recall@10?",
            "What is the reported NDCG@10?",
            "Compare mrr@100 across runs.",
        ],
    )
    def test_metric_at_k_patterns_anchor_the_query(self, query):
        assert route(query) == "entity_anchored"

    @pytest.mark.parametrize(
        "query",
        [
            "What retrieval tools does the A-RAG framework provide?",
            "Where is bge-m3 used for embedding?",
            "Does BERT4Rec appear anywhere?",
            "What is the RAG pipeline made of?",
        ],
    )
    def test_acronym_and_hyphenated_artefacts_anchor_the_query(self, query):
        assert route(query) == "entity_anchored"

    @pytest.mark.parametrize(
        "query", ["Is state-of-the-art retrieval worth it?", "Explain the cross-encoder reranker."]
    )
    def test_ordinary_hyphenated_words_are_not_artefacts(self, query):
        assert route(query) == "semantic"


class TestOutOfDomainRoute:
    @pytest.mark.parametrize(
        "query",
        [
            "What is the best pizza recipe?",
            "Hello, how are you today?",
            "What is the weather tomorrow?",
            "Tell me a joke",
        ],
    )
    def test_chit_chat_and_everyday_questions_are_rejected(self, query):
        assert route(query) == "out_of_domain"


class TestSemanticIsTheDefault:
    @pytest.mark.parametrize(
        "query",
        [
            "How do the authors justify their chunk boundaries?",
            "Why does interleaving reasoning with search help at all?",
            "What happens when the reranker is removed?",
        ],
    )
    def test_ordinary_research_questions_are_semantic(self, query):
        assert route(query) == "semantic"

    @pytest.mark.parametrize(
        "query",
        [
            "Is baking the index offline still worth the trouble for a small corpus?",
            "What is the recipe the authors follow to build their training data?",
        ],
    )
    def test_unusual_research_wording_falls_through_to_semantic_not_out_of_domain(self, query):
        assert route(query) == "semantic"

    def test_an_empty_query_is_semantic(self):
        assert route("") == "semantic"


class TestCaseInsensitivity:
    def test_shouting_a_computable_question_still_routes_to_computable(self):
        assert route("HOW MANY PAPERS IN THE CORPUS WERE PUBLISHED IN 2026?") == "computable"

    def test_shouting_an_out_of_domain_question_still_routes_out_of_domain(self):
        assert route("WHAT IS THE BEST PIZZA RECIPE?") == "out_of_domain"

    def test_lowercased_metrics_still_anchor_the_query(self):
        assert route("which run has the better recall@10 score?") == "entity_anchored"

    def test_a_shouted_research_question_is_not_mistaken_for_an_acronym(self):
        assert route("WHAT DOES THE PAPER SAY ABOUT CHUNK BOUNDARIES?") == "semantic"
