"""Alert ORM."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db import Base


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    employee_id: Mapped[str] = mapped_column(String(64), index=True)
    account_id: Mapped[str] = mapped_column(String(64), index=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    display_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="open")
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), index=True
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )
    assigned_to: Mapped[str | None] = mapped_column(String(128), nullable=True)
    shap_factors: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    top_signal: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source: Mapped[str] = mapped_column(String(16), default="seed")  # seed | replay | manual

    __table_args__ = (
        Index("ix_alerts_status_triggered", "status", "triggered_at"),
        Index("ix_alerts_employee_status", "employee_id", "status"),
    )
