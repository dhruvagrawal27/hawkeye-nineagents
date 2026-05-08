"""Graph queries — neighbourhoods, hubs, clusters."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.auth import CurrentUser
from app.deps import require_analyst
from app.schemas import GraphEdge, GraphNode, GraphResponse
from app.services.graph_service import graph_service

router = APIRouter()


def _to_response(d: dict) -> GraphResponse:
    return GraphResponse(
        nodes=[GraphNode(**n) for n in d.get("nodes", [])],
        edges=[GraphEdge(**e) for e in d.get("edges", []) if e.get("source") and e.get("target")],
    )


@router.get("/{employee_id}", response_model=GraphResponse)
async def neighbourhood(
    employee_id: str,
    user: CurrentUser = Depends(require_analyst),
    depth: int = Query(2, ge=1, le=3),
) -> GraphResponse:
    return _to_response(await graph_service.neighbourhood(employee_id, depth=depth))


@router.get("", response_model=GraphResponse)
async def overview(
    user: CurrentUser = Depends(require_analyst),
    min_score: float = Query(0.16, ge=0.0, le=1.0),
    limit: int = Query(200, ge=1, le=500),
) -> GraphResponse:
    return _to_response(await graph_service.top_risk_subgraph(min_score=min_score, limit_employees=limit))


@router.get("/hubs", response_model=list[dict])
async def hubs(
    user: CurrentUser = Depends(require_analyst),
    top_n: int = Query(10, ge=1, le=50),
) -> list[dict]:
    return await graph_service.hubs(top_n=top_n)
