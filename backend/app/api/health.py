"""Health, readiness, prometheus metrics."""

from __future__ import annotations

import time

from fastapi import APIRouter
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from app.config import settings
from app.schemas import ReadyResponse, ServiceHealth
from app.services.attestation_service import attestation_service
from app.services.embedding_service import embedding_service
from app.services.feature_aggregator import feature_aggregator
from app.services.graph_service import graph_service
from app.services.scoring import scoring_service

router = APIRouter()

_llm_last_ok_at: float | None = None
_llm_last_failure_at: float | None = None


def mark_groq_ok() -> None:
    """Kept for backwards compatibility with callers; records an LLM-OK timestamp."""
    global _llm_last_ok_at
    _llm_last_ok_at = time.time()


def mark_groq_failure() -> None:
    """Kept for backwards compatibility; records an LLM-failure timestamp."""
    global _llm_last_failure_at
    _llm_last_failure_at = time.time()


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

    # LLM service health — generic across providers. When LLM_PROVIDER=nearai
    # and the TEE attestation is fresh, the dot's tooltip surfaces it as a
    # confidential-compute lane instead of a raw vendor name.
    provider = settings.LLM_PROVIDER.lower()
    if attestation_service.is_attested:
        # Always report ok when we hold a live TEE attestation, even before
        # the first inference call has landed (attestation = the gateway is up
        # and producing valid TDX quotes — that IS the LLM-path health signal).
        services["llm"] = ServiceHealth(
            status="ok",
            detail="confidential-AI · TEE-attested",
        )
    elif _llm_last_ok_at is None and _llm_last_failure_at is None:
        services["llm"] = ServiceHealth(status="degraded", detail=f"{provider} · no calls yet")
    elif _llm_last_ok_at and (time.time() - _llm_last_ok_at) < 300:
        services["llm"] = ServiceHealth(status="ok", detail=provider)
    else:
        services["llm"] = ServiceHealth(
            status="degraded",
            detail=f"{provider} · last_ok={_llm_last_ok_at}, last_fail={_llm_last_failure_at}",
        )

    overall = "ok" if all(s.status == "ok" for s in services.values()) else "degraded"
    embeddings_block = {
        "enabled": embedding_service.enabled,
        "has_thgnn": embedding_service.has_thgnn,
        "has_simclr": embedding_service.has_simclr,
        "fusion_weights": embedding_service.fusion_weights if embedding_service.enabled else None,
        "metadata": embedding_service.metadata.to_dict() if embedding_service.enabled else None,
    }

    # LLM provider + TEE attestation surface — verifiable by the panel.
    provider = settings.LLM_PROVIDER.lower()
    if provider == "nearai":
        model = settings.NEAR_AI_MODEL
        gateway = settings.NEAR_AI_BASE_URL
    else:
        model = settings.GROQ_MODEL
        gateway = "https://api.groq.com/openai/v1"
    llm_block = {
        "provider": provider,
        "model": model,
        "gateway": gateway,
        "tee_attested": attestation_service.is_attested,
        "attestation": attestation_service.snapshot.to_dict() if attestation_service.is_attested else None,
    }

    return ReadyResponse(
        status=overall,
        services=services,
        threshold=scoring_service.threshold,
        model_version=str(scoring_service.model_card.get("version", "v1")),
        embeddings=embeddings_block,
        llm=llm_block,
    )


@router.get("/metrics")
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get("/attestation")
async def attestation() -> dict:
    """Public endpoint exposing the TEE attestation snapshot for the LLM
    gateway. Lets a reviewer independently verify that investigation memos
    are processed inside a hardware-attested confidential enclave.
    """
    await attestation_service.refresh()  # cheap; refresh-on-read keeps it fresh
    snap = attestation_service.snapshot.to_dict()
    return {
        "tee_attested": attestation_service.is_attested,
        "provider": settings.LLM_PROVIDER,
        "gateway": settings.NEAR_AI_BASE_URL if settings.LLM_PROVIDER == "nearai" else None,
        "model": settings.NEAR_AI_MODEL if settings.LLM_PROVIDER == "nearai" else None,
        **snap,
    }
