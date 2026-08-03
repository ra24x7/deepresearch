"""Write path: fetch → parse → chunk → enrich → embed → index, one paper per task.

Per-paper dynamic mapping is deliberate: docling reloads models per paper and
accumulates memory, so each paper gets its own task process. It also means a
failure retries one paper's stage rather than re-paying for the whole batch.

Trigger with params, e.g. {"corpus": "evalv1", "arxiv_ids": ["2602.03442"]},
or leave arxiv_ids empty to pull the category/date window.
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.decorators import task
from airflow.operators.python import PythonOperator

from dag_tasks.report import write_run_report
from dag_tasks.tasks import (
    embed_and_index,
    enrich,
    index_entities,
    parse_and_chunk,
    resolve_arxiv_ids,
    setup_indices,
)

default_args = {
    "owner": "deepresearch",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
}

with DAG(
    "paper_ingestion",
    default_args=default_args,
    description="Ingest arXiv papers: parse, chunk, enrich, embed, index",
    start_date=datetime(2026, 8, 1),
    # Manual-trigger only while the corpus is being built: every run costs money,
    # so automatic daily ingestion is a production decision, not a default. A
    # paused DAG cannot execute manual runs either, so the schedule — not the
    # pause toggle — is what keeps spending deliberate.
    schedule=None,
    catchup=False,
    max_active_runs=1,
    tags=["phase2", "ingestion"],
    params={
        "corpus": "prod",
        "arxiv_ids": [],
        "category": "cs.IR",
        "from_date": "20260101",
        "to_date": "20261231",
        "max_results": 10,
    },
) as dag:
    resolve = PythonOperator(task_id="resolve_arxiv_ids", python_callable=resolve_arxiv_ids)
    indices = PythonOperator(task_id="setup_indices", python_callable=setup_indices)

    @task(task_id="parse_and_chunk", max_active_tis_per_dag=2)
    def parse_and_chunk_task(arxiv_id: str, **context):
        return parse_and_chunk(arxiv_id, **context)

    @task(task_id="enrich", max_active_tis_per_dag=2)
    def enrich_task(stats: dict, **context):
        return enrich(stats["arxiv_id"], **context)

    @task(task_id="embed_and_index", max_active_tis_per_dag=2)
    def embed_and_index_task(stats: dict, **context):
        return embed_and_index(stats["arxiv_id"], **context)

    entities = PythonOperator(task_id="index_entities", python_callable=index_entities)
    report = PythonOperator(task_id="write_run_report", python_callable=write_run_report)

    parsed = parse_and_chunk_task.expand(arxiv_id=resolve.output)
    enriched = enrich_task.expand(stats=parsed)
    indexed = embed_and_index_task.expand(stats=enriched)

    indices >> parsed
    indexed >> entities >> report
