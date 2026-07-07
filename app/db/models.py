from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DomainRecord(Base):
    __tablename__ = "domain_records"
    __table_args__ = (
        Index("ix_domain_records_type_state", "record_type", "state"),
        Index("ix_domain_records_symbol_created", "symbol", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    record_type: Mapped[str] = mapped_column(String(50), nullable=False)
    symbol: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
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
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OhlcvCandleRecord(Base):
    __tablename__ = "ohlcv_candles"
    __table_args__ = (
        UniqueConstraint(
            "source",
            "symbol",
            "interval",
            "open_time",
            name="uq_ohlcv_source_symbol_interval_open",
        ),
        Index(
            "ix_ohlcv_symbol_interval_open",
            "symbol",
            "interval",
            "open_time",
        ),
        Index("ix_ohlcv_source_close", "source", "close_time"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    symbol: Mapped[str] = mapped_column(String(100), nullable=False)
    interval: Mapped[str] = mapped_column(String(10), nullable=False)
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    close_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open_price: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    high_price: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    low_price: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    close_price: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    volume: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    turnover: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
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


class SupportZoneRecord(Base):
    __tablename__ = "support_zones"
    __table_args__ = (
        Index(
            "ix_support_zones_symbol_interval_confirmed",
            "symbol",
            "interval",
            "confirmed_at",
        ),
        Index("ix_support_zones_state_updated", "state", "updated_at"),
    )

    zone_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    symbol: Mapped[str] = mapped_column(String(100), nullable=False)
    interval: Mapped[str] = mapped_column(String(10), nullable=False)
    zone_low: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    zone_high: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    state: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at_evidence: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    last_test_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    touch_count: Mapped[int] = mapped_column(Integer, nullable=False)
    rejection_count: Mapped[int] = mapped_column(Integer, nullable=False)
    strength_score: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    evidence_open_times: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False)
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


class StructureEventRecord(Base):
    __tablename__ = "structure_events"
    __table_args__ = (
        Index(
            "ix_structure_events_symbol_interval_observed",
            "symbol",
            "interval",
            "observed_at",
        ),
        Index("ix_structure_events_zone_observed", "zone_id", "observed_at"),
        Index("ix_structure_events_state_observed", "state", "observed_at"),
    )

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    zone_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    symbol: Mapped[str] = mapped_column(String(100), nullable=False)
    interval: Mapped[str] = mapped_column(String(10), nullable=False)
    state: Mapped[str] = mapped_column(String(30), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    candle_open_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    close_price: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    zone_low: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    zone_high: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    distance_bps: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    body_fraction: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    volume_ratio: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    invalidates_event_id: Mapped[str | None] = mapped_column(String(64))
    reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False)
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
