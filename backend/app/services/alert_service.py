"""Alert creation, deduplication, and dispatch.

Dedup rule (single source of truth — see ARCHITECTURE.md §5):
  Do NOT create a new alert for the same employee_id within
  ALERT_DEDUP_WINDOW_MINUTES UNLESS the new score is >= existing
  open alert's score + ALERT_DEDUP_DELTA. When deduped, we update
  the existing alert in place (touch last_seen_at, max(score)).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.alert import Alert
from app.models.employee import Employee
from app.services.scoring import ScoreResult
from app.ws.manager import ws_manager

log = structlog.get_logger(__name__)


def _employee_id_from_account(account_id: str) -> str:
    if account_id.startswith("ACC_"):
        return "EMP_" + account_id[4:]
    if account_id.startswith("ACCT_"):
        return "EMP_" + account_id[5:]
    return f"EMP_{account_id}"


_DEPT_POOL = (
    "Operations",
    "Risk",
    "Compliance",
    "Treasury",
    "Retail",
    "Branch Banking",
    "Trade Finance",
    "Audit",
)


async def _ensure_employee(db: AsyncSession, employee_id: str, account_id: str) -> None:
    """Auto-create a stub employee row if the live event references an
    employee that wasn't in the seed. Without this the /employees/{id}
    detail page 404s for any synthetic-replay employee, breaking the
    alert -> drill-down flow during demos.

    Department is derived deterministically from the employee_id so the
    same id always lands in the same department (stable across reruns).
    """
    existing = await db.get(Employee, employee_id)
    if existing is not None:
        return
    # Stable hash: sum of digits in the id mod len(pool)
    digits = "".join(c for c in employee_id if c.isdigit()) or "0"
    bucket = sum(int(c) for c in digits) % len(_DEPT_POOL)
    db.add(
        Employee(
            id=employee_id,
            account_id=account_id,
            display_name=employee_id.replace("EMP_", "Employee "),
            department=_DEPT_POOL[bucket],
            is_mule_seed=0,
        )
    )
    # Caller's commit will flush this insert.


async def find_existing_open_alert(
    db: AsyncSession, employee_id: str, window_minutes: int
) -> Alert | None:
    cutoff = datetime.now(UTC) - timedelta(minutes=window_minutes)
    stmt = (
        select(Alert)
        .where(
            Alert.employee_id == employee_id,
            Alert.status == "open",
            Alert.triggered_at >= cutoff,
        )
        .order_by(desc(Alert.triggered_at))
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_or_update_alert(
    db: AsyncSession,
    *,
    account_id: str,
    score_result: ScoreResult,
    source: str = "replay",
) -> tuple[Alert, bool]:
    """Returns (alert, is_new). If existing open alert within dedup window
    has score within ALERT_DEDUP_DELTA, we update its last_seen_at and (if
    higher) its score, return is_new=False. Otherwise create new alert."""
    employee_id = _employee_id_from_account(account_id)
    await _ensure_employee(db, employee_id, account_id)
    existing = await find_existing_open_alert(db, employee_id, settings.ALERT_DEDUP_WINDOW_MINUTES)

    factors_payload = [f.to_dict() for f in score_result.factors]
    top_signal = score_result.factors[0].name_human if score_result.factors else None

    if existing is not None and (score_result.score - existing.score) < settings.ALERT_DEDUP_DELTA:
        existing.last_seen_at = datetime.now(UTC)
        if score_result.score > existing.score:
            existing.score = score_result.score
            existing.display_score = score_result.display_score
            existing.risk_level = score_result.risk_level
            existing.shap_factors = factors_payload  # type: ignore[assignment]
            existing.top_signal = top_signal
            existing.lgb_blend = score_result.lgb_blend
            existing.thgnn_proba = score_result.thgnn_proba
            existing.simclr_proba = score_result.simclr_proba
        await db.commit()
        log.info(
            "alert.deduped",
            alert_id=existing.id,
            employee_id=employee_id,
            score=score_result.score,
            existing_score=existing.score,
        )
        # Broadcast as 'alert.updated' so the UI can refresh the row without
        # firing a new toast (toasts only fire on alert.new).
        await broadcast_event(
            {
                "type": "alert.updated",
                "alert": {
                    "id": existing.id,
                    "employee_id": existing.employee_id,
                    "account_id": existing.account_id,
                    "score": existing.score,
                    "display_score": existing.display_score,
                    "risk_level": existing.risk_level,
                    "status": existing.status,
                    "top_signal": existing.top_signal,
                    "last_seen_at": existing.last_seen_at.isoformat() if existing.last_seen_at else None,
                },
            }
        )
        return existing, False

    alert = Alert(
        employee_id=employee_id,
        account_id=account_id,
        score=score_result.score,
        display_score=score_result.display_score,
        risk_level=score_result.risk_level,
        status="open",
        triggered_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
        shap_factors=factors_payload,
        top_signal=top_signal,
        source=source,
        lgb_blend=score_result.lgb_blend,
        thgnn_proba=score_result.thgnn_proba,
        simclr_proba=score_result.simclr_proba,
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)

    log.warning(
        "ALERT.created",
        alert_id=alert.id,
        employee_id=employee_id,
        account_id=account_id,
        score=score_result.score,
        risk_level=score_result.risk_level,
        source=source,
    )

    await broadcast_alert(alert)
    return alert, True


async def broadcast_alert(alert: Alert) -> None:
    payload: dict[str, Any] = {
        "type": "alert.new",
        "alert": {
            "id": alert.id,
            "employee_id": alert.employee_id,
            "account_id": alert.account_id,
            "score": alert.score,
            "display_score": alert.display_score,
            "risk_level": alert.risk_level,
            "status": alert.status,
            "top_signal": alert.top_signal,
            "triggered_at": alert.triggered_at.isoformat() if alert.triggered_at else None,
            "source": alert.source,
            "shap_factors": json.loads(json.dumps(alert.shap_factors, default=str))
            if alert.shap_factors
            else None,
            "lgb_blend": alert.lgb_blend,
            "thgnn_proba": alert.thgnn_proba,
            "simclr_proba": alert.simclr_proba,
        },
    }
    await ws_manager.broadcast(payload)


async def broadcast_event(payload: dict[str, Any]) -> None:
    """Generic broadcast for non-alert events (e.g. replay status changes, stats ticks)."""
    await ws_manager.broadcast(payload)
