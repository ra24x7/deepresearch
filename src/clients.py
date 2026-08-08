"""Configured service handles: Bedrock runtime, OpenSearch, Postgres sessions.

Every caller went through the same three-line ritual (parse the OpenSearch host
out of a URL, pin the same boto3 timeouts, wrap an engine in a sessionmaker),
which is how the eval scripts drifted onto a hardcoded localhost:9200 while the
DAG read OPENSEARCH__HOST. Building a client is settings-driven and lives here.
"""

from typing import Any

import boto3
from botocore.config import Config
from opensearchpy import OpenSearch
from sqlalchemy.orm import sessionmaker

from config import BedrockSettings, EmbeddingSettings, OpenSearchSettings, PostgresSettings
from db.session import get_engine, get_session_factory
from ingestion.embeddings.base import EmbeddingProvider
from ingestion.embeddings.factory import build_provider

REQUEST_TIMEOUT_SECONDS = 120
_DEFAULT_OPENSEARCH_PORT = 9200
_FAKE_PROVIDER = "fake"


def bedrock_runtime_client(region: str | None = None, timeout: float = REQUEST_TIMEOUT_SECONDS) -> Any:
    return boto3.client(
        "bedrock-runtime",
        region_name=region or BedrockSettings().region,
        config=Config(read_timeout=timeout, connect_timeout=timeout),
    )


def opensearch_client(
    settings: OpenSearchSettings | None = None, timeout: float = REQUEST_TIMEOUT_SECONDS
) -> OpenSearch:
    host = (settings or OpenSearchSettings()).host.replace("http://", "").replace("https://", "")
    hostname, _, port = host.partition(":")
    return OpenSearch(hosts=[{"host": hostname, "port": int(port or _DEFAULT_OPENSEARCH_PORT)}], timeout=timeout)


def postgres_session_factory(settings: PostgresSettings | None = None) -> sessionmaker:
    return get_session_factory(get_engine(settings or PostgresSettings()))


def embedding_provider(
    settings: EmbeddingSettings | None = None, bedrock_client: Any = None
) -> EmbeddingProvider:
    """The configured provider, given a Bedrock client only when one is needed —
    EMBEDDING__PROVIDER=fake must run the whole path without credentials.
    Callers that already hold a client pass it in rather than opening a second.
    """
    settings = settings or EmbeddingSettings()
    if settings.provider == _FAKE_PROVIDER:
        return build_provider(settings, None)
    return build_provider(settings, bedrock_client or bedrock_runtime_client())
