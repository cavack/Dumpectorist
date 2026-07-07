"""Create normalized reclaim attempts table.

Revision ID: 20260707_0004
Revises: 20260707_0003
Create Date: 2026-07-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260707_0004"
down_revision: str | None = "20260707_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reclaim_attempts",
        sa.Column("attempt_id", sa.String(length=64), nullable=False),
        sa.Column("break_event_id", sa.String(length=64), nullable=False),
        sa.Column("zone_id", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("symbol", sa.String(length=100), nullable=False),
        sa.Column("structure_interval", sa.String(length=10), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outcome", sa.String(length=30), nullable=False),
        sa.Column("setup_type", sa.String(length=40), nullable=False),
        sa.Column("readiness", sa.String(length=30), nullable=False),
        sa.Column("zone_low", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("zone_high", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("maximum_price", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column(
            "maximum_penetration_bps",
            sa.Numeric(precision=18, scale=4),
            nullable=False,
        ),
        sa.Column("duration_bars", sa.Integer(), nullable=False),
        sa.Column("closes_above_zone", sa.Integer(), nullable=False),
        sa.Column("bars_above_zone", sa.Integer(), nullable=False),
        sa.Column("bounce_volume_ratio", sa.Numeric(precision=18, scale=6)),
        sa.Column("rejection_candle_open_time", sa.DateTime(timezone=True)),
        sa.Column("rejection_low", sa.Numeric(precision=38, scale=18)),
        sa.Column("trigger_candle_open_time", sa.DateTime(timezone=True)),
        sa.Column("quality_score", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("attempt_id"),
    )
    op.create_index(
        "ix_reclaim_attempts_symbol_observed",
        "reclaim_attempts",
        ["symbol", "observed_at"],
    )
    op.create_index(
        "ix_reclaim_attempts_readiness_observed",
        "reclaim_attempts",
        ["readiness", "observed_at"],
    )
    op.create_index(
        "ix_reclaim_attempts_break_event_observed",
        "reclaim_attempts",
        ["break_event_id", "observed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_reclaim_attempts_break_event_observed",
        table_name="reclaim_attempts",
    )
    op.drop_index(
        "ix_reclaim_attempts_readiness_observed",
        table_name="reclaim_attempts",
    )
    op.drop_index(
        "ix_reclaim_attempts_symbol_observed",
        table_name="reclaim_attempts",
    )
    op.drop_table("reclaim_attempts")
