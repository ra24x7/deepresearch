import json
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from config import RerankSettings
from retrieval.rerank.cohere_bedrock import CohereBedrockReranker
from retrieval.rerank.exceptions import RerankInvocationError, UnknownRerankerError
from retrieval.rerank.factory import build_reranker
from retrieval.rerank.identity import IdentityReranker
from retrieval.schemas import FusedHit

SETTINGS = RerankSettings(model_id="cohere.rerank-v3-5:0", region="eu-central-1", max_documents=100)


def _hit(doc_id: str, score: float, text: str = "some text") -> FusedHit:
    return FusedHit(doc_id=doc_id, arxiv_id="2602.03442", score=score, text=text, channels=("dense_chunks",))


def _response(results: list[dict]) -> dict:
    body = MagicMock()
    body.read.return_value = json.dumps({"results": results}).encode()
    return {"body": body}


class TestIdentityReranker:
    def test_returns_the_first_n_unchanged(self):
        hits = [_hit("a", 3.0), _hit("b", 2.0), _hit("c", 1.0)]

        out = IdentityReranker().rerank("q", hits, top_n=2)

        assert [h.doc_id for h in out] == ["a", "b"]

    def test_model_id_marks_it_as_a_stand_in(self):
        assert IdentityReranker().model_id == "identity"


class TestCohereBedrockReranker:
    def test_sends_query_and_document_texts_to_the_model(self):
        client = MagicMock()
        client.invoke_model.return_value = _response([{"index": 0, "relevance_score": 0.9}])

        CohereBedrockReranker(client, SETTINGS).rerank("my query", [_hit("a", 1.0, "alpha text")], top_n=1)

        _, kwargs = client.invoke_model.call_args
        payload = json.loads(kwargs["body"])
        assert kwargs["modelId"] == "cohere.rerank-v3-5:0"
        assert payload["query"] == "my query"
        assert payload["documents"] == ["alpha text"]
        assert payload["top_n"] == 1

    def test_reorders_hits_by_model_relevance_not_prior_score(self):
        client = MagicMock()
        # the model prefers the hit that fusion ranked last
        client.invoke_model.return_value = _response(
            [{"index": 2, "relevance_score": 0.99}, {"index": 0, "relevance_score": 0.10}]
        )
        hits = [_hit("a", 9.0), _hit("b", 8.0), _hit("c", 7.0)]

        out = CohereBedrockReranker(client, SETTINGS).rerank("q", hits, top_n=2)

        assert [h.doc_id for h in out] == ["c", "a"]
        assert out[0].score == pytest.approx(0.99)

    def test_reranked_hits_keep_their_provenance(self):
        client = MagicMock()
        client.invoke_model.return_value = _response([{"index": 0, "relevance_score": 0.5}])

        out = CohereBedrockReranker(client, SETTINGS).rerank("q", [_hit("a", 1.0)], top_n=1)

        assert out[0].channels == ("dense_chunks",)
        assert out[0].arxiv_id == "2602.03442"

    def test_empty_hits_short_circuit_without_calling_the_model(self):
        client = MagicMock()

        out = CohereBedrockReranker(client, SETTINGS).rerank("q", [], top_n=5)

        assert out == []
        client.invoke_model.assert_not_called()

    def test_document_count_is_capped_to_protect_the_request(self):
        client = MagicMock()
        client.invoke_model.return_value = _response([{"index": 0, "relevance_score": 0.5}])
        settings = RerankSettings(model_id="cohere.rerank-v3-5:0", region="eu-central-1", max_documents=2)

        CohereBedrockReranker(client, settings).rerank("q", [_hit(str(i), 1.0) for i in range(5)], top_n=2)

        payload = json.loads(client.invoke_model.call_args[1]["body"])
        assert len(payload["documents"]) == 2

    def test_api_failure_is_wrapped_in_a_typed_error(self):
        client = MagicMock()
        client.invoke_model.side_effect = ClientError(
            {"Error": {"Code": "ValidationException", "Message": "boom"}}, "InvokeModel"
        )

        with pytest.raises(RerankInvocationError):
            CohereBedrockReranker(client, SETTINGS).rerank("q", [_hit("a", 1.0)], top_n=1)


class TestFactory:
    def test_builds_the_identity_reranker_without_a_client(self):
        assert build_reranker(RerankSettings(provider="identity")).model_id == "identity"

    def test_builds_the_cohere_reranker_when_given_a_client(self):
        reranker = build_reranker(SETTINGS, MagicMock())

        assert reranker.model_id == "cohere.rerank-v3-5:0"

    def test_unknown_provider_raises(self):
        with pytest.raises(UnknownRerankerError):
            build_reranker(RerankSettings(provider="nope"))


class TestSectionTitleContext:
    def test_section_title_is_sent_with_the_chunk_text(self):
        # a chunk's own section heading often carries the terms the body omits:
        # "F. A troubleshooting-oriented knowledge graph" anchors a chunk whose
        # text says only "The graph contains 96,517 nodes...".
        client = MagicMock()
        client.invoke_model.return_value = _response([{"index": 0, "relevance_score": 0.9}])
        hit = FusedHit(
            doc_id="a", arxiv_id="x", score=1.0, text="The graph contains 96,517 nodes.",
            channels=("dense_chunks",), section_title="F. A troubleshooting-oriented knowledge graph",
        )

        CohereBedrockReranker(client, SETTINGS).rerank("q", [hit], top_n=1)

        document = json.loads(client.invoke_model.call_args[1]["body"])["documents"][0]
        assert "troubleshooting-oriented knowledge graph" in document
        assert "96,517" in document

    def test_a_hit_without_a_section_title_sends_text_alone(self):
        client = MagicMock()
        client.invoke_model.return_value = _response([{"index": 0, "relevance_score": 0.9}])

        CohereBedrockReranker(client, SETTINGS).rerank("q", [_hit("a", 1.0, "bare text")], top_n=1)

        assert json.loads(client.invoke_model.call_args[1]["body"])["documents"] == ["bare text"]
