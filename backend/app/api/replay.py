"""Replay control endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth import CurrentUser
from app.deps import require_analyst
from app.schemas import ReplayStartRequest, ReplayStatus
from app.services.replay_service import replay_service

router = APIRouter()


@router.post("/start", response_model=dict)
async def start(
    body: ReplayStartRequest,
    user: CurrentUser = Depends(require_analyst),
) -> dict:
    return await replay_service.start(mode=body.mode, rate=body.rate)


@router.post("/stop", response_model=dict)
async def stop(user: CurrentUser = Depends(require_analyst)) -> dict:
    return await replay_service.stop()


@router.post("/inject-burst", response_model=dict)
async def inject_burst(
    user: CurrentUser = Depends(require_analyst),
    n_events: int = 50,
    top_mules: int = 5,
) -> dict:
    return await replay_service.inject_burst(n_events=n_events, top_mules=top_mules)


@router.get("/status", response_model=ReplayStatus)
async def status(user: CurrentUser = Depends(require_analyst)) -> ReplayStatus:
    s = await replay_service.status()
    return ReplayStatus(status=s["status"], stats=s.get("stats", {}))
