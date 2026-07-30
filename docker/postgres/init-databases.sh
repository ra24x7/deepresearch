#!/bin/sh
# Runs once on first boot of an empty data volume (docker-entrypoint-initdb.d).
# POSTGRES_DB=deepresearch is created by the image; add the Airflow metadata DB.
# POSIX sh — the alpine postgres image has no bash.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE airflow;
    GRANT ALL PRIVILEGES ON DATABASE airflow TO $POSTGRES_USER;
EOSQL
