"""Add fusion-component columns to alerts (lgb_blend, thgnn_proba, simclr_proba).

Revision ID: 0002_alert_fusion
Revises: 0001_initial
Create Date: 2026-05-11 00:00:00

These three columns are NULLable so existing alerts (created before T-HGNN /
SimCLR fusion shipped) remain valid. New alerts populate them when the
embedding_service is enabled. The frontend uses NULL → "fusion data not
available" and renders the legacy "raw blend" view as a fallback.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_alert_fusion"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("alerts", sa.Column("lgb_blend", sa.Float, nullable=True))
    op.add_column("alerts", sa.Column("thgnn_proba", sa.Float, nullable=True))
    op.add_column("alerts", sa.Column("simclr_proba", sa.Float, nullable=True))


def downgrade() -> None:
    op.drop_column("alerts", "simclr_proba")
    op.drop_column("alerts", "thgnn_proba")
    op.drop_column("alerts", "lgb_blend")
