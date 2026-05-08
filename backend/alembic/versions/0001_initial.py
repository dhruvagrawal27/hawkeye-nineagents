"""Initial schema — alerts, narratives, employees, score_history, audit_log.

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-08 00:00:00

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("employee_id", sa.String(64), nullable=False),
        sa.Column("account_id", sa.String(64), nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("display_score", sa.Float, nullable=False, server_default="0"),
        sa.Column("risk_level", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), server_default="open"),
        sa.Column("triggered_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("assigned_to", sa.String(128), nullable=True),
        sa.Column("shap_factors", sa.JSON, nullable=True),
        sa.Column("top_signal", sa.String(128), nullable=True),
        sa.Column("source", sa.String(16), server_default="seed"),
    )
    op.create_index("ix_alerts_employee_id", "alerts", ["employee_id"])
    op.create_index("ix_alerts_account_id", "alerts", ["account_id"])
    op.create_index("ix_alerts_triggered_at", "alerts", ["triggered_at"])
    op.create_index("ix_alerts_status_triggered", "alerts", ["status", "triggered_at"])
    op.create_index("ix_alerts_employee_status", "alerts", ["employee_id", "status"])

    op.create_table(
        "narratives",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "alert_id",
            sa.Integer,
            sa.ForeignKey("alerts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("model_version", sa.String(64), server_default=""),
        sa.Column("is_fallback", sa.Boolean, server_default=sa.false()),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_narratives_alert_id", "narratives", ["alert_id"])

    op.create_table(
        "employees",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("account_id", sa.String(64), nullable=False, unique=True),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("department", sa.String(32), nullable=False),
        sa.Column("is_mule_seed", sa.Integer, server_default="0"),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_employees_account_id", "employees", ["account_id"])

    op.create_table(
        "score_history",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("employee_id", sa.String(64), nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("display_score", sa.Float, nullable=False, server_default="0"),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_score_history_employee_id", "score_history", ["employee_id"])
    op.create_index("ix_score_history_recorded_at", "score_history", ["recorded_at"])

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "alert_id",
            sa.Integer,
            sa.ForeignKey("alerts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("employee_id", sa.String(64), nullable=True),
        sa.Column("actor", sa.String(128), server_default="system"),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("detail", sa.Text, nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_log_alert_id", "audit_log", ["alert_id"])
    op.create_index("ix_audit_log_employee_id", "audit_log", ["employee_id"])
    op.create_index("ix_audit_log_occurred_at", "audit_log", ["occurred_at"])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("score_history")
    op.drop_table("employees")
    op.drop_table("narratives")
    op.drop_table("alerts")
