"""Shared, cached service handles for ingestion tasks.

Package name deliberately not `ingestion` — the dags folder is on sys.path and
would shadow src/ingestion.

Every knob comes from the settings classes or DAG params; nothing about what
gets fetched or how it is processed is hardcoded here.
"""

from functools import lru_cache
from pathlib import Path

import boto3
from botocore.config import Config
from opensearchpy import OpenSearch

from config import BedrockSettings, EmbeddingSettings, OpenSearchSettings, PostgresSettings
from db.session import get_engine, get_session_factory
from ingestion.embeddings.factory import build_provider
from llm.bedrock import invoke_json
from pipeline.stages import default_pipeline_settings

PAPERS_DIR = Path("/opt/airflow/data/papers")
_REQUEST_TIMEOUT_SECONDS = 120


@lru_cache(maxsize=1)
def session_factory():
    return get_session_factory(get_engine(PostgresSettings()))


@lru_cache(maxsize=1)
def pipeline_settings():
    return default_pipeline_settings()


@lru_cache(maxsize=1)
def bedrock_client():
    settings = BedrockSettings()
    return boto3.client(
        "bedrock-runtime",
        region_name=settings.region,
        config=Config(read_timeout=_REQUEST_TIMEOUT_SECONDS, connect_timeout=_REQUEST_TIMEOUT_SECONDS),
    )


@lru_cache(maxsize=1)
def search_client():
    host = OpenSearchSettings().host.replace("http://", "").replace("https://", "")
    hostname, _, port = host.partition(":")
    return OpenSearch(hosts=[{"host": hostname, "port": int(port or 9200)}], timeout=_REQUEST_TIMEOUT_SECONDS)


@lru_cache(maxsize=1)
def embedding_provider():
    settings = EmbeddingSettings()
    client = None if settings.provider == "fake" else bedrock_client()
    return build_provider(settings, client)


def llm_invoke_json(prompt: str):
    return invoke_json(prompt, bedrock_client(), pipeline_settings().enrichment)
