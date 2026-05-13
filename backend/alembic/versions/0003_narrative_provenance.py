"""Add provider + tee_attested provenance columns to narratives.

Revision ID: 0003_narrative_provenance
Revises: 0002_alert_fusion
Create Date: 2026-05-13 00:00:00

Captures which LLM provider generated each investigation memo and whether
it was processed inside a TEE-attested gateway. Nullable so legacy
narratives (generated before NEAR AI Cloud was wired in) remain valid.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_narrative_provenance"
down_revision = "0002_alert_fusion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("narratives", sa.Column("provider", sa.String(16), nullable=True))
    op.add_column("narratives", sa.Column("tee_attested", sa.Boolean, nullable=True))


def downgrade() -> None:
    op.drop_column("narratives", "tee_attested")
    op.drop_column("narratives", "provider")
