"""HAWKEYE FastAPI app entrypoint with lifespan-managed singletons."""

from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.api import alerts as alerts_api
from app.api import employees as employees_api
from app.api import graph as graph_api
from app.api import health as health_api
from app.api import narrative as narrative_api
from app.api import replay as replay_api
from app.api import stats as stats_api
from app.api import ws_routes
from app.config import settings
from app.consumers.event_consumer import event_consumer
from app.logging_setup import configure_logging
from app.models.db import dispose_engine, init_engine
from app.services.feature_aggregator import feature_aggregator
from app.services.graph_service import graph_service
from app.services.scoring import scoring_service

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    configure_logging()
    log.info("hawkeye.boot", preflight=settings.is_preflight_mode)

    init_engine()

    # Scoring service: load + warm + bootstrap (fail-fast)
    scoring_service.load()
    try:
        scoring_service.warm_shap()
    except Exception as exc:
        log.warning("hawkeye.shap_warm_failed", error=str(exc))
    try:
        scoring_service.assert_bootstrap(n_rows=100, tolerance=0.05)
    except Exception as exc:
        # Don't kill the service if matrix isn't on disk in dev — log loudly
        log.warning("hawkeye.bootstrap_assert_skipped_or_failed", error=str(exc))

    # Connect Redis (best-effort)
    try:
        await feature_aggregator.connect()
    except Exception as exc:
        log.warning("hawkeye.redis_connect_failed", error=str(exc))

    # Connect Neo4j (best-effort — graph upserts will retry on first event)
    try:
        await graph_service.connect()
    except Exception as exc:
        log.warning("hawkeye.neo4j_connect_failed", error=str(exc))

    # Start the Kafka consumer background task
    try:
        await event_consumer.start()
    except Exception as exc:
        log.warning("hawkeye.consumer_start_failed", error=str(exc))

    log.info("hawkeye.ready")
    try:
        yield
    finally:
        log.info("hawkeye.shutdown")
        try:
            await event_consumer.stop()
        except Exception:
            pass
        try:
            await graph_service.close()
        except Exception:
            pass
        try:
            await feature_aggregator.close()
        except Exception:
            pass
        await dispose_engine()


app = FastAPI(
    title="HAWKEYE API",
    description="Real-time insider-fraud detection (NINEAGENTS)",
    version="0.1.0",
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_preflight_mode else [settings.PUBLIC_BASE_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- routers --------------------------------------------------------------
app.include_router(health_api.router, tags=["health"])
app.include_router(alerts_api.router, prefix="/alerts", tags=["alerts"])
app.include_router(employees_api.router, prefix="/employees", tags=["employees"])
app.include_router(graph_api.router, prefix="/graph", tags=["graph"])
app.include_router(narrative_api.router, prefix="/narrative", tags=["narrative"])
app.include_router(replay_api.router, prefix="/replay", tags=["replay"])
app.include_router(stats_api.router, prefix="/stats", tags=["stats"])
app.include_router(alerts_api.internal_router, prefix="/internal", tags=["internal"])
app.include_router(ws_routes.router, prefix="/ws", tags=["ws"])


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {
        "service": "hawkeye-backend",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/healthz",
        "ready": "/readyz",
    }
