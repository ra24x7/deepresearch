#!/bin/bash
set -e

# Remove stale PID files from any previous container run
rm -f ${AIRFLOW_HOME}/airflow-webserver.pid
rm -f ${AIRFLOW_HOME}/airflow-scheduler.pid

# Initialise / migrate Airflow metadata database
echo "Initializing Airflow database..."
airflow db migrate

# Sync FAB permissions FIRST so roles (Admin, Viewer, etc.) exist before user create.
echo "Syncing Airflow FAB permissions..."
airflow sync-perm

# Create admin user (idempotent — skips silently if already exists)
echo "Creating admin user..."
airflow users create \
    --username admin \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@example.com \
    --password admin || echo "Admin user already exists"

# Start webserver in background (no --daemon to keep it as a child process),
# then run scheduler in foreground so Docker tracks the container's main process.
echo "Starting Airflow webserver and scheduler..."
airflow webserver --port 8080 &
airflow scheduler
