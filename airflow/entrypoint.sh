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

# Create admin user (idempotent — skips silently if already exists).
# An Airflow admin can run arbitrary code in a task, where the Bedrock key
# lives, so the password comes from the environment and is never defaulted.
if [ -z "${AIRFLOW_ADMIN_PASSWORD}" ]; then
    echo "AIRFLOW_ADMIN_PASSWORD is not set — refusing to create an admin user." >&2
    exit 1
fi
if [ ${#AIRFLOW_ADMIN_PASSWORD} -lt 12 ] || [ "${AIRFLOW_ADMIN_PASSWORD}" = "admin" ]; then
    echo "AIRFLOW_ADMIN_PASSWORD must be at least 12 characters and not 'admin'." >&2
    exit 1
fi

echo "Creating admin user..."
airflow users create \
    --username "${AIRFLOW_ADMIN_USERNAME:-admin}" \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email "${AIRFLOW_ADMIN_EMAIL:-admin@example.com}" \
    --password "${AIRFLOW_ADMIN_PASSWORD}" || echo "Admin user already exists"

# Start webserver in background (no --daemon to keep it as a child process),
# then run scheduler in foreground so Docker tracks the container's main process.
echo "Starting Airflow webserver and scheduler..."
airflow webserver --port 8080 &
airflow scheduler
