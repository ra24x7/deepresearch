import os
from datetime import datetime, timedelta

import httpx
import psycopg2
from airflow import DAG
from airflow.operators.python import PythonOperator

REQUIRED_ENV_VARS = ["AWS_BEARER_TOKEN_BEDROCK", "POSTGRES__DSN", "OPENSEARCH__HOST"]


def check_opensearch():
    host = os.environ["OPENSEARCH__HOST"]
    response = httpx.get(f"{host}/_cluster/health", timeout=10)
    response.raise_for_status()
    status = response.json()["status"]
    if status not in ("green", "yellow"):
        raise RuntimeError(f"OpenSearch cluster unhealthy: {status}")
    print(f"OpenSearch: {status}")
    return status


def check_postgres():
    conn = psycopg2.connect(os.environ["POSTGRES__DSN"])
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
    finally:
        conn.close()
    print("Postgres: connected")
    return "connected"


def check_config():
    missing = [name for name in REQUIRED_ENV_VARS if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"Missing required env vars: {missing}")
    print(f"Config: all {len(REQUIRED_ENV_VARS)} required env vars present")
    return "ok"


default_args = {
    "owner": "deepresearch",
    "depends_on_past": False,
    "start_date": datetime(2026, 7, 1),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
}

dag = DAG(
    "stack_healthcheck",
    default_args=default_args,
    description="Verify OpenSearch, Postgres, and config are reachable from a task",
    schedule=None,
    catchup=False,
    tags=["phase2", "infra"],
)

opensearch_task = PythonOperator(task_id="check_opensearch", python_callable=check_opensearch, dag=dag)
postgres_task = PythonOperator(task_id="check_postgres", python_callable=check_postgres, dag=dag)
config_task = PythonOperator(task_id="check_config", python_callable=check_config, dag=dag)

opensearch_task >> postgres_task >> config_task
