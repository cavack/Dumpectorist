"""Create support zones and structure events tables.

Revision ID: 20260707_0003
Revises: 20260707_0002
Create Date: 2026-07-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260707_0003"
down_revision: str | None = "20260707_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "support_zones",
        sa.Column("zone_id", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("symbol", sa.String(length=100), nullable=False),
        sa.Column("interval", sa.String(length=10), nullable=False),
        sa.Column("zone_low", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("zone_high", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("state", sa.String(length=30), nullable=False),
        sa.Column("created_at_evidence", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_test_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("touch_count", sa.Integer(), nullable=False),
        sa.Column("rejection_count", sa.Integer(), nullable=False),
        sa.Column("strength_score", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("evidence_open_times", sa.JSON(), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("zone_id"),
    )
    op.create_index(
        "ix_support_zones_symbol_interval_confirmed",
        "support_zones",
        ["symbol", "interval", "confirmed_at"],
    )
    op.create_index(
        "ix_support_zones_state_updated",
        "support_zones",
        ["state", "updated_at"],
    )

    op.create_table(
        "structure_events",
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("zone_id", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("symbol", sa.String(length=100), nullable=False),
        sa.Column("interval", sa.String(length=10), nullable=False),
        sa.Column("state", sa.String(length=30), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("candle_open_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("close_price", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("zone_low", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("zone_high", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("distance_bps", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("body_fraction", sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column("volume_ratio", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("invalidates_event_id", sa.String(length=64), nullable=True),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(
        "ix_structure_events_symbol_interval_observed",
        "structure_events",
        ["symbol", "interval", "observed_at"],
    )
    op.create_index(
        "ix_structure_events_zone_observed",
        "structure_events",
        ["zone_id", "observed_at"],
    )
    op.create_index(
        "ix_structure_events_state_observed",
        "structure_events",
        ["state", "observed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_structure_events_state_observed", table_name="structure_events")
    op.drop_index("ix_structure_events_zone_observed", table_name="structure_events")
    op.drop_index(
        "ix_structure_events_symbol_interval_observed",
        table_name="structure_events",
    )
    op.drop_table("structure_events")
    op.drop_index("ix_support_zones_state_updated", table_name="support_zones")
    op.drop_index(
        "ix_support_zones_symbol_interval_confirmed",
        table_name="support_zones",
    )
    op.drop_table("support_zones")
