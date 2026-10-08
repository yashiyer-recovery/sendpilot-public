"""campaign.record_ids — the approved records a campaign sends

Revision ID: 0003_campaign_records
Revises: 0002_rls
Create Date: 2026-06-22
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_campaign_records"
down_revision = "0002_rls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "campaign",
        sa.Column("record_ids", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'")),
    )


def downgrade() -> None:
    op.drop_column("campaign", "record_ids")
