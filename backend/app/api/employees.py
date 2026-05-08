"""Employee directory + timeline + score history."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.deps import db_session, require_analyst
from app.models.alert import Alert
from app.models.employee import Employee, ScoreHistory
from app.schemas import AlertOut, EmployeeOut, ScorePoint

router = APIRouter()


@router.get("", response_model=list[EmployeeOut])
async def list_employees(
    db: AsyncSession = Depends(db_session),
    user: CurrentUser = Depends(require_analyst),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    department: str | None = None,
    risk_min: float | None = None,
) -> list[EmployeeOut]:
    stmt = select(Employee).limit(limit).offset(offset)
    if department:
        stmt = stmt.where(Employee.department == department)
    rows = (await db.execute(stmt)).scalars().all()

    # Latest score from score_history; latest open alert per employee
    employees: list[EmployeeOut] = []
    for emp in rows:
        latest_score_row = (
            await db.execute(
                select(ScoreHistory)
                .where(ScoreHistory.employee_id == emp.id)
                .order_by(desc(ScoreHistory.recorded_at))
                .limit(1)
            )
        ).scalar_one_or_none()
        open_count = (
            await db.scalar(
                select(func.count(Alert.id)).where(
                    Alert.employee_id == emp.id, Alert.status == "open"
                )
            )
            or 0
        )
        risk_score = float(latest_score_row.score) if latest_score_row else None
        if risk_min is not None and (risk_score is None or risk_score < risk_min):
            continue
        from app.services.risk_levels import score_to_display, score_to_level
        from app.services.scoring import scoring_service

        employees.append(
            EmployeeOut(
                id=emp.id,
                account_id=emp.account_id,
                display_name=emp.display_name,
                department=emp.department,
                is_mule_seed=int(emp.is_mule_seed),
                risk_score=risk_score,
                display_score=(
                    score_to_display(risk_score, scoring_service.threshold)
                    if risk_score is not None
                    else None
                ),
                risk_level=(
                    score_to_level(risk_score, scoring_service.threshold)
                    if risk_score is not None
                    else None
                ),
                open_alert_count=int(open_count),
            )
        )
    return employees


@router.get("/top", response_model=list[EmployeeOut])
async def top_risk(
    db: AsyncSession = Depends(db_session),
    user: CurrentUser = Depends(require_analyst),
    limit: int = Query(10, ge=1, le=100),
) -> list[EmployeeOut]:
    """Top-N employees by their highest open-alert score."""
    stmt = (
        select(
            Alert.employee_id,
            Alert.account_id,
            func.max(Alert.score).label("max_score"),
            func.count(Alert.id).label("n"),
        )
        .where(Alert.status == "open")
        .group_by(Alert.employee_id, Alert.account_id)
        .order_by(desc("max_score"))
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    out: list[EmployeeOut] = []
    for r in rows:
        emp = await db.get(Employee, r.employee_id)
        if emp is None:
            continue
        from app.services.risk_levels import score_to_display, score_to_level
        from app.services.scoring import scoring_service

        out.append(
            EmployeeOut(
                id=emp.id,
                account_id=emp.account_id,
                display_name=emp.display_name,
                department=emp.department,
                is_mule_seed=int(emp.is_mule_seed),
                risk_score=float(r.max_score),
                display_score=score_to_display(float(r.max_score), scoring_service.threshold),
                risk_level=score_to_level(float(r.max_score), scoring_service.threshold),
                open_alert_count=int(r.n),
            )
        )
    return out


@router.get("/{employee_id}", response_model=EmployeeOut)
async def get_employee(
    employee_id: str,
    db: AsyncSession = Depends(db_session),
    user: CurrentUser = Depends(require_analyst),
) -> EmployeeOut:
    emp = await db.get(Employee, employee_id)
    if emp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="employee not found")
    latest = (
        await db.execute(
            select(ScoreHistory)
            .where(ScoreHistory.employee_id == employee_id)
            .order_by(desc(ScoreHistory.recorded_at))
            .limit(1)
        )
    ).scalar_one_or_none()
    open_count = (
        await db.scalar(
            select(func.count(Alert.id)).where(
                Alert.employee_id == employee_id, Alert.status == "open"
            )
        )
        or 0
    )
    from app.services.risk_levels import score_to_display, score_to_level
    from app.services.scoring import scoring_service

    risk_score = float(latest.score) if latest else None
    return EmployeeOut(
        id=emp.id,
        account_id=emp.account_id,
        display_name=emp.display_name,
        department=emp.department,
        is_mule_seed=int(emp.is_mule_seed),
        risk_score=risk_score,
        display_score=(score_to_display(risk_score, scoring_service.threshold) if risk_score is not None else None),
        risk_level=(
            score_to_level(risk_score, scoring_service.threshold) if risk_score is not None else None
        ),
        open_alert_count=int(open_count),
    )


@router.get("/{employee_id}/score-history", response_model=list[ScorePoint])
async def score_history(
    employee_id: str,
    db: AsyncSession = Depends(db_session),
    user: CurrentUser = Depends(require_analyst),
    days: int = Query(30, ge=1, le=180),
) -> list[ScorePoint]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        await db.execute(
            select(ScoreHistory)
            .where(ScoreHistory.employee_id == employee_id, ScoreHistory.recorded_at >= cutoff)
            .order_by(ScoreHistory.recorded_at)
        )
    ).scalars().all()
    return [ScorePoint(recorded_at=r.recorded_at, score=r.score, display_score=r.display_score) for r in rows]


@router.get("/{employee_id}/alerts", response_model=list[AlertOut])
async def alerts_for_employee(
    employee_id: str,
    db: AsyncSession = Depends(db_session),
    user: CurrentUser = Depends(require_analyst),
    limit: int = Query(50, ge=1, le=200),
) -> list[AlertOut]:
    rows = (
        await db.execute(
            select(Alert)
            .where(Alert.employee_id == employee_id)
            .order_by(desc(Alert.triggered_at))
            .limit(limit)
        )
    ).scalars().all()
    return [AlertOut.from_orm_row(r) for r in rows]
