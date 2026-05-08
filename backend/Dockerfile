# syntax=docker/dockerfile:1.7
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120

# librdkafka for confluent-kafka, libgomp for lightgbm
RUN apt-get update -qq && apt-get install -y --no-install-recommends \
      build-essential \
      curl \
      libgomp1 \
      librdkafka-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ---- Cached dependency layer ----------------------------------------------
# Install Python deps first using a stub package skeleton. This layer ONLY
# rebuilds when pyproject.toml changes, so subsequent app/* edits skip the
# 3-minute shap/lightgbm/numba install.
COPY pyproject.toml ./
RUN mkdir -p app && \
    printf '"""stub for hatchling build"""\n' > app/__init__.py && \
    pip install --upgrade pip && \
    pip install ".[dev]" && \
    rm -rf app

# ---- App source layer (cheap to invalidate) -------------------------------
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./
# Re-install just the local package (deps already present) so /app/app is on
# the import path with the latest source.
RUN pip install . --no-deps

# Bind-mounted at runtime; create the dirs so import-time path checks pass.
RUN mkdir -p /app/artifacts /app/data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
