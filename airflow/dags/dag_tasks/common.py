"""Per-process caching of the service handles ingestion tasks need.

Package name deliberately not `ingestion` — the dags folder is on sys.path and
would shadow src/ingestion.

How a client is built lives in src/clients.py; this module only memoizes it, so
a task process opens one connection each and the DAG cannot drift onto
different hosts or timeouts than the scripts use.
"""

from functools import lru_cache
from pathlib import Path

import clients
from llm.bedrock import invoke_json
from pipeline.stages import default_pipeline_settings

PAPERS_DIR = Path("/opt/airflow/data/papers")

session_factory = lru_cache(maxsize=1)(clients.postgres_session_factory)
bedrock_client = lru_cache(maxsize=1)(clients.bedrock_runtime_client)
search_client = lru_cache(maxsize=1)(clients.opensearch_client)


@lru_cache(maxsize=1)
def pipeline_settings():
    return default_pipeline_settings()


@lru_cache(maxsize=1)
def embedding_provider():
    return clients.embedding_provider(bedrock_client=bedrock_client())


def llm_invoke_json(prompt: str):
    return invoke_json(prompt, bedrock_client(), pipeline_settings().enrichment)
