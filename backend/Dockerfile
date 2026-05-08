# syntax=docker/dockerfile:1.7
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# librdkafka for confluent-kafka, libgomp for lightgbm
RUN apt-get update -qq && apt-get install -y --no-install-recommends \
      build-essential \
      curl \
      libgomp1 \
      librdkafka-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy package source first (hatchling needs app/ to build the wheel)
COPY pyproject.toml ./
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./

RUN pip install --upgrade pip && pip install ".[dev]"

# Bind-mounted at runtime; create the dirs so import-time path checks pass.
RUN mkdir -p /app/artifacts /app/data

EXPOSE 8000

# uvicorn workers=1 because scoring service holds a singleton in memory
# and we run replay/consumer as a single background task per process.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
