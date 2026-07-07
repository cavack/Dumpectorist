from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, DateTime, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models import utc_now


class ReclaimAttemptRecord(Base):
    __tablename__ = "reclaim_attempts"
    __table_args__ = (
        Index(
            "ix_reclaim_attempts_symbol_observed",
            "symbol",
            "observed_at",
        ),
        Index(
            "ix_reclaim_attempts_readiness_observed",
            "readiness",
            "observed_at",
        ),
        Index(
            "ix_reclaim_attempts_break_event_observed",
            "break_event_id",
            "observed_at",
        ),
    )

    attempt_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    break_event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    zone_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    symbol: Mapped[str] = mapped_column(String(100), nullable=False)
    structure_interval: Mapped[str] = mapped_column(String(10), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    outcome: Mapped[str] = mapped_column(String(30), nullable=False)
    setup_type: Mapped[str] = mapped_column(String(40), nullable=False)
    readiness: Mapped[str] = mapped_column(String(30), nullable=False)
    zone_low: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    zone_high: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    maximum_price: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    maximum_penetration_bps: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
    )
    duration_bars: Mapped[int] = mapped_column(Integer, nullable=False)
    closes_above_zone: Mapped[int] = mapped_column(Integer, nullable=False)
    bars_above_zone: Mapped[int] = mapped_column(Integer, nullable=False)
    bounce_volume_ratio: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    rejection_candle_open_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    rejection_low: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    trigger_candle_open_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    quality_score: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    warnings: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
