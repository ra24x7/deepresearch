FROM python:3.12-slim

# ── uv ────────────────────────────────────────────────────────────────────────
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# ── env ───────────────────────────────────────────────────────────────────────
ENV AIRFLOW_HOME=/opt/airflow \
    AIRFLOW_VERSION=2.10.3 \
    PYTHON_VERSION=3.12

ENV CONSTRAINT_URL="https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"

# UV settings for Docker:
#   UV_LINK_MODE=copy   — Docker layers live on different filesystems; copy
#                          prevents "can't hardlink across filesystems" errors.
#   UV_COMPILE_BYTECODE — pre-compile .pyc files for faster container startup.
#   UV_PYTHON_DOWNLOADS — use the interpreter from python:3.12-slim, not uv's.
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

# ── system deps ───────────────────────────────────────────────────────────────
# poppler/tesseract/libgl are Docling (PDF parsing) runtime requirements.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
        libpq-dev \
        poppler-utils \
        tesseract-ocr \
        libgl1 \
        libglib2.0-0 \
        libxcb1 \
        libx11-6 \
    && rm -rf /var/lib/apt/lists/*

# ── airflow user ──────────────────────────────────────────────────────────────
RUN groupadd -r -g 50000 airflow && \
    useradd -r -u 50000 -g airflow -d ${AIRFLOW_HOME} -s /bin/bash airflow

RUN mkdir -p ${AIRFLOW_HOME}/dags ${AIRFLOW_HOME}/logs ${AIRFLOW_HOME}/data && \
    chown -R 50000:50000 ${AIRFLOW_HOME} && \
    chmod -R 755 ${AIRFLOW_HOME}

# ── Airflow core ──────────────────────────────────────────────────────────────
# The official constraint file pins every transitive dep for this version pair.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system \
        "apache-airflow[postgres]==${AIRFLOW_VERSION}" \
        --constraint "${CONSTRAINT_URL}" \
        psycopg2-binary

# ── CPU-only PyTorch ──────────────────────────────────────────────────────────
# Installed from the CPU wheel index BEFORE requirements-airflow.txt so the
# resolver sees torch satisfied and never pulls the ~4 GB CUDA variant.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system \
        torch torchvision torchaudio \
        --index-url https://download.pytorch.org/whl/cpu

# ── project requirements ──────────────────────────────────────────────────────
COPY airflow/requirements-airflow.txt /tmp/requirements-airflow.txt
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system \
        -r /tmp/requirements-airflow.txt

# ── application source ────────────────────────────────────────────────────────
# In Docker Compose, src/ and dags/ are bind-mounted at runtime; these copies
# are the fallback so the image is self-contained off-compose (e.g. K8s later).
COPY src /opt/airflow/src
COPY airflow/dags /opt/airflow/dags

# ── entrypoint ────────────────────────────────────────────────────────────────
COPY airflow/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER airflow
WORKDIR ${AIRFLOW_HOME}

EXPOSE 8080

CMD ["/entrypoint.sh"]
