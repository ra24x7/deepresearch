import json
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from config import EmbeddingSettings
from ingestion.embeddings.cohere_bedrock import CohereBedrockProvider
from ingestion.embeddings.exceptions import EmbeddingInvocationError

SETTINGS = EmbeddingSettings(model_id="global.cohere.embed-v4:0", dimension=4)


def _response(vectors: list[list[float]]) -> dict:
    body = MagicMock()
    body.read.return_value = json.dumps({"embeddings": {"float": vectors}}).encode()
    return {"body": body}


def _client_error() -> ClientError:
    return ClientError({"Error": {"Code": "ValidationException", "Message": "boom"}}, "InvokeModel")


class TestEmbedPassages:
    def test_sends_search_document_input_type_and_model_id(self):
        client = MagicMock()
        client.invoke_model.return_value = _response([[0.1, 0.2, 0.3, 0.4]])

        CohereBedrockProvider(client, SETTINGS).embed_passages(["one text"])

        _, kwargs = client.invoke_model.call_args
        payload = json.loads(kwargs["body"])
        assert payload["input_type"] == "search_document"
        assert kwargs["modelId"] == SETTINGS.model_id

    def test_sends_embedding_types_and_output_dimension_from_settings(self):
        client = MagicMock()
        client.invoke_model.return_value = _response([[0.1, 0.2, 0.3, 0.4]])

        CohereBedrockProvider(client, SETTINGS).embed_passages(["one text"])

        _, kwargs = client.invoke_model.call_args
        payload = json.loads(kwargs["body"])
        assert payload["embedding_types"] == ["float"]
        assert payload["output_dimension"] == SETTINGS.dimension

    def test_returns_parsed_embeddings_in_order(self):
        client = MagicMock()
        client.invoke_model.return_value = _response([[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8]])

        result = CohereBedrockProvider(client, SETTINGS).embed_passages(["a", "b"])

        assert result == [[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8]]

    def test_batches_input_into_slices_of_96(self):
        client = MagicMock()

        def _side_effect(**kwargs):
            texts = json.loads(kwargs["body"])["texts"]
            return _response([[0.0, 0.0, 0.0, 0.0]] * len(texts))

        client.invoke_model.side_effect = _side_effect
        texts = [f"text {i}" for i in range(200)]

        result = CohereBedrockProvider(client, SETTINGS).embed_passages(texts)

        assert len(result) == 200
        assert client.invoke_model.call_count == 3
        call_sizes = [len(json.loads(c.kwargs["body"])["texts"]) for c in client.invoke_model.call_args_list]
        assert call_sizes == [96, 96, 8]

    def test_empty_input_makes_no_api_call(self):
        client = MagicMock()

        result = CohereBedrockProvider(client, SETTINGS).embed_passages([])

        assert result == []
        client.invoke_model.assert_not_called()

    def test_wraps_client_error_in_typed_error(self):
        client = MagicMock()
        client.invoke_model.side_effect = _client_error()

        with pytest.raises(EmbeddingInvocationError):
            CohereBedrockProvider(client, SETTINGS).embed_passages(["a"])


class TestEmbedQuery:
    def test_sends_search_query_input_type_and_single_text(self):
        client = MagicMock()
        client.invoke_model.return_value = _response([[0.1, 0.2, 0.3, 0.4]])

        CohereBedrockProvider(client, SETTINGS).embed_query("a question")

        _, kwargs = client.invoke_model.call_args
        payload = json.loads(kwargs["body"])
        assert payload["input_type"] == "search_query"
        assert payload["texts"] == ["a question"]

    def test_returns_single_vector(self):
        client = MagicMock()
        client.invoke_model.return_value = _response([[0.1, 0.2, 0.3, 0.4]])

        result = CohereBedrockProvider(client, SETTINGS).embed_query("a question")

        assert result == [0.1, 0.2, 0.3, 0.4]

    def test_wraps_client_error_in_typed_error(self):
        client = MagicMock()
        client.invoke_model.side_effect = _client_error()

        with pytest.raises(EmbeddingInvocationError):
            CohereBedrockProvider(client, SETTINGS).embed_query("a question")
