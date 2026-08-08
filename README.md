# DeepResearch

Production-grade RAG for academic research, built eval-first.
See `doc/` for spec, architecture, and the living roadmap (`doc/project-status.md`).

## Quickstart

```bash
uv sync                                      # local env (Python 3.13)
cp .env.example .env                         # fill in every blank value

docker compose up -d --build                 # OpenSearch + Postgres + Airflow
docker compose ps                            # wait for 4/4 healthy
```

`.env` needs `AWS_BEARER_TOKEN_BEDROCK` plus three secrets compose refuses to
start without — `POSTGRES_PASSWORD`, `AIRFLOW_ADMIN_PASSWORD` (≥12 chars) and
`AIRFLOW_SECRET_KEY`.

- Airflow UI: http://localhost:8080 (`admin` / `AIRFLOW_ADMIN_PASSWORD`)
- OpenSearch: http://localhost:9200 — Dashboards: http://localhost:5601
- Postgres: localhost:5433 (`deepresearch` app DB + `airflow` metadata DB)

Every published port binds to `127.0.0.1`: OpenSearch runs with its security
plugin disabled and Airflow admin can execute code in a task that holds the
Bedrock key, so neither is safe to expose beyond the host. Serving this stack
on a network needs real authentication first, not a port change.

Smoke test: trigger the `stack_healthcheck` DAG in the Airflow UI (or
`docker compose exec airflow airflow dags test stack_healthcheck`) — three
tasks verify OpenSearch, Postgres, and required config from inside a task.

Tests: `uv run pytest` (DAG-import tests need Airflow, which requires
Python ≤3.12, so they skip locally on 3.13). The equivalent in-container
gate: `docker compose exec airflow airflow dags list-import-errors`
must report no errors.
