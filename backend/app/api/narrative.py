"""Narrative get + on-demand regeneration."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.deps import db_session, require_analyst
from app.models.alert import Alert
from app.models.narrative import Narrative
from app.schemas import NarrativeOut
from app.services.feature_aggregator import feature_aggregator
from app.services.graph_service import graph_service
from app.services.narrative_service import narrative_service
from app.services.scoring import scoring_service

router = APIRouter()


@router.get("/{alert_id}", response_model=NarrativeOut)
async def get_narrative(
    alert_id: int,
    db: AsyncSession = Depends(db_session),
    user: CurrentUser = Depends(require_analyst),
) -> NarrativeOut:
    n = (
        await db.execute(
            select(Narrative).where(Narrative.alert_id == alert_id).order_by(desc(Narrative.id)).limit(1)
        )
    ).scalar_one_or_none()
    if n is None:
        # Lazy-generate if missing
        return await regenerate(alert_id, db=db, user=user)
    return NarrativeOut(
        alert_id=n.alert_id,
        body=n.body,
        model_version=n.model_version,
        is_fallback=n.is_fallback,
        latency_ms=n.latency_ms,
        generated_at=n.generated_at,
        provider=n.provider,
        tee_attested=n.tee_attested,
    )


@router.post("/{alert_id}/regenerate", response_model=NarrativeOut)
async def regenerate(
    alert_id: int,
    db: AsyncSession = Depends(db_session),
    user: CurrentUser = Depends(require_analyst),
) -> NarrativeOut:
    alert = await db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="alert not found")

    factors = list(alert.shap_factors) if alert.shap_factors else []
    base = await feature_aggregator.get_base_features(alert.account_id) or {}
    behaviour = {
        "n_txn": int(float(base.get("n", 0) or 0)),
        "pass_rate_pct": int(float(base.get("pass_rate", 0) or 0) * 100),
        "pngt_pct": int(float(base.get("pngt", 0) or 0) * 100),
        "ps49_pct": int(float(base.get("ps49", 0) or 0) * 100),
        "fan_ratio": round(float(base.get("fan_ratio", 1) or 1), 2),
        "shared_systems": 0,
        "flagged_peers": 0,
    }
    try:
        shared = await graph_service.shared_systems(alert.employee_id)
        if shared:
            behaviour["shared_systems"] = len(shared)
            peers: set[str] = set()
            for r in shared:
                peers.update(r.get("peers", []))
            behaviour["flagged_peers"] = len(peers)
    except Exception:
        pass

    result = await narrative_service.generate(
        employee_id=alert.employee_id,
        score=float(alert.display_score),
        raw_score=float(alert.score),
        risk_level=alert.risk_level,
        threshold=scoring_service.threshold,
        factors=factors,
        behaviour=behaviour,
    )
    n = Narrative(
        alert_id=alert.id,
        body=result.body,
        model_version=result.model_version,
        is_fallback=result.is_fallback,
        latency_ms=result.latency_ms,
        provider=result.provider,
        tee_attested=result.tee_attested,
    )
    db.add(n)
    await db.commit()
    await db.refresh(n)

    if not result.is_fallback:
        from app.api.health import mark_groq_ok

        mark_groq_ok()
    else:
        from app.api.health import mark_groq_failure

        mark_groq_failure()

    return NarrativeOut(
        alert_id=n.alert_id,
        body=n.body,
        model_version=n.model_version,
        is_fallback=n.is_fallback,
        latency_ms=n.latency_ms,
        generated_at=n.generated_at,
        provider=n.provider,
        tee_attested=n.tee_attested,
    )
