"""Health, readiness, prometheus metrics."""

from __future__ import annotations

import time

from fastapi import APIRouter
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from app.config import settings
from app.schemas import ReadyResponse, ServiceHealth
from app.services.feature_aggregator import feature_aggregator
from app.services.graph_service import graph_service
from app.services.scoring import scoring_service

router = APIRouter()

_groq_last_ok_at: float | None = None
_groq_last_failure_at: float | None = None


def mark_groq_ok() -> None:
    global _groq_last_ok_at
    _groq_last_ok_at = time.time()


def mark_groq_failure() -> None:
    global _groq_last_failure_at
    _groq_last_failure_at = time.time()


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz", response_model=ReadyResponse)
async def readyz() -> ReadyResponse:
    services: dict[str, ServiceHealth] = {}

    # Postgres
    from sqlalchemy import text

    try:
        from app.models.db import get_engine

        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        services["postgres"] = ServiceHealth(status="ok")
    except Exception as exc:
        services["postgres"] = ServiceHealth(status="down", detail=str(exc)[:80])

    # Redis
    try:
        await feature_aggregator.connect()
        await feature_aggregator.client.ping()
        services["redis"] = ServiceHealth(status="ok")
    except Exception as exc:
        services["redis"] = ServiceHealth(status="down", detail=str(exc)[:80])

    # Neo4j
    services["neo4j"] = ServiceHealth(
        status="ok" if await graph_service.health() else "down"
    )

    # Kafka — best-effort: try a one-shot AdminClient metadata
    try:
        from confluent_kafka.admin import AdminClient

        ac = AdminClient({"bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS})
        meta = ac.list_topics(timeout=2.0)
        services["kafka"] = ServiceHealth(
            status="ok" if settings.KAFKA_TOPIC_EVENTS in meta.topics else "degraded",
            detail=f"topics={len(meta.topics)}",
        )
    except Exception as exc:
        services["kafka"] = ServiceHealth(status="down", detail=str(exc)[:80])

    # Groq — track last call timestamp
    if _groq_last_ok_at is None and _groq_last_failure_at is None:
        services["groq"] = ServiceHealth(status="degraded", detail="no calls yet")
    elif _groq_last_ok_at and (time.time() - _groq_last_ok_at) < 300:
        services["groq"] = ServiceHealth(status="ok")
    else:
        services["groq"] = ServiceHealth(
            status="degraded",
            detail=f"last_ok={_groq_last_ok_at}, last_fail={_groq_last_failure_at}",
        )

    overall = "ok" if all(s.status == "ok" for s in services.values()) else "degraded"
    return ReadyResponse(
        status=overall,
        services=services,
        threshold=scoring_service.threshold,
        model_version=str(scoring_service.model_card.get("version", "v1")),
    )


@router.get("/metrics")
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
