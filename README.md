# DeepResearch

Production-grade RAG for academic research, built eval-first.
See `doc/` for spec, architecture, and the living roadmap (`doc/project-status.md`).

## Quickstart

```bash
uv sync                                      # local env (Python 3.13)
cp .env.example .env                         # fill in AWS_BEARER_TOKEN_BEDROCK

docker compose up -d --build                 # OpenSearch + Postgres + Airflow
docker compose ps                            # wait for 4/4 healthy
```

- Airflow UI: http://localhost:8080 (admin / admin)
- OpenSearch: http://localhost:9200 — Dashboards: http://localhost:5601
- Postgres: localhost:5433 (`deepresearch` app DB + `airflow` metadata DB)

Smoke test: trigger the `stack_healthcheck` DAG in the Airflow UI (or
`docker compose exec airflow airflow dags test stack_healthcheck`) — three
tasks verify OpenSearch, Postgres, and required config from inside a task.

Tests: `uv run pytest` (DAG-import tests need Airflow, which requires
Python ≤3.12, so they skip locally on 3.13). The equivalent in-container
gate: `docker compose exec airflow airflow dags list-import-errors`
must report no errors.
