"""Create normalized OHLCV candles table.

Revision ID: 20260707_0002
Revises: 20260707_0001
Create Date: 2026-07-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260707_0002"
down_revision: str | None = "20260707_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ohlcv_candles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("symbol", sa.String(length=100), nullable=False),
        sa.Column("interval", sa.String(length=10), nullable=False),
        sa.Column("open_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("close_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open_price", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("high_price", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("low_price", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("close_price", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("volume", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("turnover", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source",
            "symbol",
            "interval",
            "open_time",
            name="uq_ohlcv_source_symbol_interval_open",
        ),
    )
    op.create_index(
        "ix_ohlcv_symbol_interval_open",
        "ohlcv_candles",
        ["symbol", "interval", "open_time"],
    )
    op.create_index(
        "ix_ohlcv_source_close",
        "ohlcv_candles",
        ["source", "close_time"],
    )


def downgrade() -> None:
    op.drop_index("ix_ohlcv_source_close", table_name="ohlcv_candles")
    op.drop_index("ix_ohlcv_symbol_interval_open", table_name="ohlcv_candles")
    op.drop_table("ohlcv_candles")
