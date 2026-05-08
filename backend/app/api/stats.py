"""Aggregate stats for dashboard cards and charts."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.deps import db_session, require_analyst
from app.models.alert import Alert
from app.schemas import StatsOverview
from app.services.feature_aggregator import feature_aggregator
from app.services.risk_levels import RiskBands
from app.services.scoring import scoring_service

router = APIRouter()


@router.get("/overview", response_model=StatsOverview)
async def overview(
    db: AsyncSession = Depends(db_session),
    user: CurrentUser = Depends(require_analyst),
) -> StatsOverview:
    cutoff_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    n_alerts_24h = (
        await db.scalar(select(func.count(Alert.id)).where(Alert.triggered_at >= cutoff_24h))
        or 0
    )
    n_high = (
        await db.scalar(
            select(func.count(func.distinct(Alert.employee_id))).where(
                Alert.status == "open",
                Alert.risk_level.in_(["HIGH", "CRITICAL"]),
            )
        )
        or 0
    )
    by_status = dict(
        (s, c) for s, c in (
            await db.execute(select(Alert.status, func.count(Alert.id)).group_by(Alert.status))
        ).all()
    )

    try:
        await feature_aggregator.connect()
        stats = await feature_aggregator.get_replay_stats()
        events_ingested = int(float(stats.get("events_published", 0)))
    except Exception:
        events_ingested = 0

    bands = RiskBands(threshold=scoring_service.threshold)
    return StatsOverview(
        total_alerts_24h=int(n_alerts_24h),
        high_risk_employees=int(n_high),
        events_ingested=events_ingested,
        detection_latency_ms=180.0,  # static placeholder; replace with histogram lookup
        alerts_open=int(by_status.get("open", 0)),
        alerts_dismissed=int(by_status.get("dismissed", 0)),
        alerts_escalated=int(by_status.get("escalated", 0)),
        alerts_investigating=int(by_status.get("investigating", 0)),
        threshold=scoring_service.threshold,
        bands={
            "low_high": bands.low_high,
            "medium_low": bands.medium_low,
            "high_low": bands.high_low,
            "critical_low": bands.critical_low,
        },
    )


@router.get("/hourly", response_model=list[dict])
async def hourly(
    db: AsyncSession = Depends(db_session),
    user: CurrentUser = Depends(require_analyst),
    hours: int = Query(168, ge=1, le=720),  # 7 days default for the heatmap
) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = (
        await db.execute(
            select(Alert.triggered_at, Alert.risk_level).where(Alert.triggered_at >= cutoff)
        )
    ).all()
    buckets: dict[str, dict[str, int]] = defaultdict(lambda: {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0, "total": 0})
    for triggered_at, risk_level in rows:
        bucket = triggered_at.replace(minute=0, second=0, microsecond=0).isoformat()
        buckets[bucket][risk_level] = buckets[bucket].get(risk_level, 0) + 1
        buckets[bucket]["total"] = buckets[bucket].get("total", 0) + 1
    return [{"hour": h, **counts} for h, counts in sorted(buckets.items())]


@router.get("/risk-distribution", response_model=list[dict])
async def risk_distribution(
    db: AsyncSession = Depends(db_session),
    user: CurrentUser = Depends(require_analyst),
) -> list[dict]:
    """Histogram of all open alert scores in 25 buckets between 0 and 1."""
    rows = (
        await db.execute(select(Alert.display_score).where(Alert.status == "open"))
    ).scalars().all()
    bins = [0.0] * 25
    for score in rows:
        idx = min(int((score or 0) * 25), 24)
        bins[idx] += 1
    return [
        {"bin_low": i * 0.04, "bin_high": (i + 1) * 0.04, "count": int(c)}
        for i, c in enumerate(bins)
    ]


@router.get("/ingestion-rate", response_model=dict)
async def ingestion_rate(user: CurrentUser = Depends(require_analyst)) -> dict:
    try:
        await feature_aggregator.connect()
        stats = await feature_aggregator.get_replay_stats()
        return {
            "events_published": int(float(stats.get("events_published", 0))),
            "alerts_fired": int(float(stats.get("alerts_fired", 0))),
            "started_at": stats.get("started_at"),
            "rate": int(float(stats.get("rate", 0))),
            "mode": stats.get("mode"),
        }
    except Exception:
        return {"events_published": 0, "alerts_fired": 0, "started_at": None, "rate": 0, "mode": None}


@router.get("/model-card", response_model=dict)
async def model_card(user: CurrentUser = Depends(require_analyst)) -> dict:
    return {
        "name": "HAWKEYE LightGBM blend (M1 clean + M2 full)",
        **scoring_service.model_card,
        "threshold": scoring_service.threshold,
        "blend_weights": scoring_service.weights,
        "n_features_full": len(scoring_service.feat_cols),
        "n_features_clean": len(scoring_service.feat_clean),
    }
