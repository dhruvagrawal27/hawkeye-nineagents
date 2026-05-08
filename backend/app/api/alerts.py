"""Alert listing, detail, triage."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user
from app.deps import db_session, require_analyst
from app.models.alert import Alert
from app.models.employee import AuditLog
from app.schemas import AlertOut, TriageRequest

router = APIRouter()


@router.get("", response_model=list[AlertOut])
async def list_alerts(
    db: AsyncSession = Depends(db_session),
    user: CurrentUser = Depends(require_analyst),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    risk_level: str | None = Query(None),
    alert_status: str | None = Query(None, alias="status"),
    employee_id: str | None = Query(None),
    since: str | None = Query(None, description="window like '60s', '5m', '24h'"),
) -> list[AlertOut]:
    stmt = select(Alert)
    if risk_level:
        stmt = stmt.where(Alert.risk_level == risk_level.upper())
    if alert_status:
        stmt = stmt.where(Alert.status == alert_status.lower())
    if employee_id:
        stmt = stmt.where(Alert.employee_id == employee_id)
    if since:
        seconds = _parse_since(since)
        if seconds is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=seconds)
            stmt = stmt.where(Alert.triggered_at >= cutoff)
    stmt = stmt.order_by(desc(Alert.triggered_at)).limit(limit).offset(offset)
    rows = (await db.execute(stmt)).scalars().all()
    return [AlertOut.from_orm_row(r) for r in rows]


@router.get("/{alert_id}", response_model=AlertOut)
async def get_alert(
    alert_id: int,
    db: AsyncSession = Depends(db_session),
    user: CurrentUser = Depends(require_analyst),
) -> AlertOut:
    alert = await db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="alert not found")
    return AlertOut.from_orm_row(alert)


@router.post("/{alert_id}/triage", response_model=AlertOut)
async def triage(
    alert_id: int,
    body: TriageRequest,
    db: AsyncSession = Depends(db_session),
    user: CurrentUser = Depends(get_current_user),
) -> AlertOut:
    alert = await db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="alert not found")

    map_status = {
        "dismiss": "dismissed",
        "investigate": "investigating",
        "escalate": "escalated",
        "reopen": "open",
    }
    alert.status = map_status[body.action]
    if body.action == "investigate":
        alert.assigned_to = user.username

    db.add(
        AuditLog(
            alert_id=alert.id,
            employee_id=alert.employee_id,
            actor=user.username,
            action=body.action,
            detail=body.note,
        )
    )
    await db.commit()
    await db.refresh(alert)
    return AlertOut.from_orm_row(alert)


def _parse_since(s: str) -> int | None:
    """Parse '60s', '5m', '24h' → seconds."""
    s = s.strip().lower()
    try:
        if s.endswith("s"):
            return int(s[:-1])
        if s.endswith("m"):
            return int(s[:-1]) * 60
        if s.endswith("h"):
            return int(s[:-1]) * 3600
        return int(s)
    except ValueError:
        return None


# --- internal endpoints (preflight only) ----------------------------------

internal_router = APIRouter()


@internal_router.post("/test-broadcast")
async def test_broadcast() -> dict[str, Any]:
    """Used by preflight WebSocket test."""
    from app.config import settings
    from app.services.alert_service import broadcast_event

    if not settings.is_preflight_mode:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="preflight only")
    payload = {"type": "test.broadcast", "ts": datetime.now(timezone.utc).isoformat()}
    await broadcast_event(payload)
    return {"sent": True}


@internal_router.post("/test-alert")
async def test_alert(
    db: AsyncSession = Depends(db_session),
) -> dict[str, Any]:
    """Used by preflight to verify alert creation + WebSocket broadcast end-to-end."""
    from app.config import settings
    from app.services.alert_service import broadcast_alert

    if not settings.is_preflight_mode:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="preflight only")
    a = Alert(
        employee_id="EMP_PREFLIGHT_TEST",
        account_id="ACCT_PREFLIGHT_TEST",
        score=0.99,
        display_score=0.99,
        risk_level="CRITICAL",
        status="open",
        top_signal="Preflight synthetic signal",
        shap_factors=[
            {
                "name": "preflight",
                "name_human": "Preflight test factor",
                "value": 1.0,
                "value_human": "1.00",
                "contribution": 0.5,
                "normal": None,
            }
        ],
        source="manual",
    )
    db.add(a)
    await db.commit()
    await db.refresh(a)
    await broadcast_alert(a)
    return {"alert_id": a.id}


@internal_router.get("/stats")
async def internal_stats(db: AsyncSession = Depends(db_session)) -> dict[str, int]:
    """Used by preflight to confirm seed populated alerts and employees."""
    n_alerts = await db.scalar(select(func.count(Alert.id))) or 0
    return {"alerts": int(n_alerts)}
