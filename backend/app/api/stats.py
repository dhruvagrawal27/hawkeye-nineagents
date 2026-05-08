"""Aggregate stats for dashboard cards and charts."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
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


@router.get("/by-department", response_model=list[dict])
async def by_department(
    db: AsyncSession = Depends(db_session),
    user: CurrentUser = Depends(require_analyst),
) -> list[dict]:
    """Alerts and risk rollup grouped by department.

    Joins alerts ↔ employees on employee_id and aggregates by department.
    """
    from sqlalchemy import case

    from app.models.employee import Employee

    stmt = (
        select(
            Employee.department.label("department"),
            func.count(Alert.id).label("total"),
            func.count(case((Alert.status == "open", 1))).label("open"),
            func.count(case((Alert.status == "investigating", 1))).label("investigating"),
            func.count(case((Alert.status == "escalated", 1))).label("escalated"),
            func.count(case((Alert.status == "dismissed", 1))).label("dismissed"),
            func.count(case((Alert.risk_level == "CRITICAL", 1))).label("critical"),
            func.count(case((Alert.risk_level == "HIGH", 1))).label("high"),
            func.max(Alert.score).label("max_score"),
            func.avg(Alert.score).label("mean_score"),
            func.count(func.distinct(Alert.employee_id)).label("unique_employees"),
        )
        .join(Alert, Employee.id == Alert.employee_id, isouter=True)
        .group_by(Employee.department)
        .order_by(func.count(case((Alert.status == "open", 1))).desc())
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "department": r.department,
            "total": int(r.total or 0),
            "open": int(r.open or 0),
            "investigating": int(r.investigating or 0),
            "escalated": int(r.escalated or 0),
            "dismissed": int(r.dismissed or 0),
            "critical": int(r.critical or 0),
            "high": int(r.high or 0),
            "max_score": float(r.max_score) if r.max_score is not None else 0.0,
            "mean_score": float(r.mean_score) if r.mean_score is not None else 0.0,
            "unique_employees": int(r.unique_employees or 0),
        }
        for r in rows
        if r.department  # skip null department (orphan alerts)
    ]


@router.get("/audit-log", response_model=list[dict])
async def audit_feed(
    db: AsyncSession = Depends(db_session),
    user: CurrentUser = Depends(require_analyst),
    limit: int = Query(50, ge=1, le=500),
) -> list[dict]:
    """Recent triage and action history. Used by the manager/audit view."""
    from app.models.employee import AuditLog

    rows = (
        await db.execute(
            select(AuditLog)
            .order_by(desc(AuditLog.occurred_at))
            .limit(limit)
        )
    ).scalars().all()
    return [
        {
            "id": r.id,
            "alert_id": r.alert_id,
            "employee_id": r.employee_id,
            "actor": r.actor,
            "action": r.action,
            "detail": r.detail,
            "occurred_at": r.occurred_at.isoformat() if r.occurred_at else None,
        }
        for r in rows
    ]


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
