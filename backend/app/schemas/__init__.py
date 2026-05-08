"""Pydantic schemas for API request/response. v2."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AlertOut(BaseModel):
    id: int
    employee_id: str
    account_id: str
    score: float
    display_score: float
    risk_level: str
    status: str
    triggered_at: datetime
    last_seen_at: datetime
    assigned_to: str | None = None
    top_signal: str | None = None
    shap_factors: list[dict[str, Any]] | None = None
    source: str

    @classmethod
    def from_orm_row(cls, alert: Any) -> "AlertOut":
        return cls(
            id=alert.id,
            employee_id=alert.employee_id,
            account_id=alert.account_id,
            score=alert.score,
            display_score=alert.display_score,
            risk_level=alert.risk_level,
            status=alert.status,
            triggered_at=alert.triggered_at,
            last_seen_at=alert.last_seen_at,
            assigned_to=alert.assigned_to,
            top_signal=alert.top_signal,
            shap_factors=list(alert.shap_factors) if alert.shap_factors else None,
            source=alert.source,
        )


class TriageRequest(BaseModel):
    action: str = Field(pattern="^(dismiss|investigate|escalate|reopen)$")
    note: str | None = None


class EmployeeOut(BaseModel):
    id: str
    account_id: str
    display_name: str
    department: str
    is_mule_seed: int = 0
    risk_score: float | None = None
    display_score: float | None = None
    risk_level: str | None = None
    open_alert_count: int = 0


class ScorePoint(BaseModel):
    recorded_at: datetime
    score: float
    display_score: float


class GraphNode(BaseModel):
    id: str
    label: str
    risk_score: float = 0.0
    risk_level: str = "LOW"
    department: str | None = None
    kind: str | None = None
    access_count: int | None = None


class GraphEdge(BaseModel):
    source: str
    target: str
    count: int = 0
    last_at: str | None = None


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class NarrativeOut(BaseModel):
    alert_id: int
    body: str
    model_version: str
    is_fallback: bool
    latency_ms: int | None = None
    generated_at: datetime


class StatsOverview(BaseModel):
    total_alerts_24h: int
    high_risk_employees: int
    events_ingested: int
    detection_latency_ms: float
    alerts_open: int
    alerts_dismissed: int
    alerts_escalated: int
    alerts_investigating: int
    threshold: float
    bands: dict[str, float]


class ReplayStartRequest(BaseModel):
    mode: str = Field(default="mule_burst", pattern="^(mule_burst|sequential)$")
    rate: int = Field(default=500, ge=1, le=10000)


class ReplayStatus(BaseModel):
    status: str
    stats: dict[str, Any]


class ServiceHealth(BaseModel):
    status: str  # ok | degraded | down
    detail: str | None = None


class ReadyResponse(BaseModel):
    status: str  # ok | degraded
    services: dict[str, ServiceHealth]
    threshold: float
    model_version: str
