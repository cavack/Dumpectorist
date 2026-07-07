from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.candles.models import CandleInterval, CandleSource
from app.db.base import Base
from app.db.models import StructureEventRecord, SupportZoneRecord
from app.signals.htf_provider import DerivedHigherTimeframeEvidenceProvider
from app.signals.models import HigherTimeframeEvidenceOrigin
from app.structure.htf_models import (
    HtfStructureAnalysis,
    StructureEvent,
    StructureEventState,
    SupportZone,
    TimeframeStructureEvidence,
    TimeframeStructureStatus,
)
from app.structure.htf_repository import HtfStructureRepository


NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


def _assert_decimal_model_equivalent(
    actual: object | None,
    expected: object | None,
    *,
    decimal_fields: tuple[str, ...],
) -> None:
    assert actual is not None
    assert expected is not None
    actual_values = vars(actual).copy()
    expected_values = vars(expected).copy()

    # SQLite's NUMERIC affinity may round-trip through a binary float. The
    # production PostgreSQL NUMERIC columns are exact, so repository tests use
    # the same tolerance as the idempotent upsert comparison for SQLite only.
    for field_name in decimal_fields:
        actual_value = actual_values.pop(field_name)
        expected_value = expected_values.pop(field_name)
        if actual_value is None or expected_value is None:
            assert actual_value is expected_value
            continue
        tolerance = max(abs(expected_value) * Decimal("1e-15"), Decimal("1e-18"))
        assert abs(actual_value - expected_value) <= tolerance

    assert actual_values == expected_values


def analysis(interval: CandleInterval, suffix: str) -> HtfStructureAnalysis:
    duration = interval.duration
    first_open = NOW - duration * 6
    second_open = NOW - duration * 3
    zone = SupportZone(
        zone_id=f"zone-{suffix}",
        source=CandleSource.BYBIT,
        symbol="BTCUSDT",
        interval=interval,
        low=Decimal("99.8"),
        high=Decimal("100.4"),
        created_at=first_open + duration,
        confirmed_at=second_open + duration * 2,
        last_test_at=second_open + duration,
        touch_count=2,
        rejection_count=2,
        strength_score=Decimal("80"),
        evidence_open_times=(first_open, second_open),
        reasons=("fixture zone",),
    )
    event = StructureEvent(
        event_id=f"event-{suffix}",
        zone_id=zone.zone_id,
        source=CandleSource.BYBIT,
        symbol="BTCUSDT",
        interval=interval,
        state=StructureEventState.CONFIRMED_BREAK,
        observed_at=NOW,
        candle_open_time=NOW - duration,
        close_price=Decimal("98"),
        zone_low=zone.low,
        zone_high=zone.high,
        distance_bps=Decimal("180"),
        body_fraction=Decimal("0.6"),
        volume_ratio=Decimal("1.5"),
        reasons=("confirmed break",),
    )
    evidence = TimeframeStructureEvidence(
        source=CandleSource.BYBIT,
        symbol="BTCUSDT",
        interval=interval,
        status=TimeframeStructureStatus.DAMAGED,
        observed_at=NOW,
        zone_id=zone.zone_id,
        event_id=event.event_id,
        reasons=("fixture evidence",),
    )
    return HtfStructureAnalysis(
        source=CandleSource.BYBIT,
        symbol="BTCUSDT",
        interval=interval,
        observed_at=NOW,
        zones=(zone,),
        primary_zone=zone,
        events=(event,),
        evidence=evidence,
    )


@pytest.mark.asyncio
async def test_repository_upsert_is_idempotent_and_provider_returns_derived_evidence():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    daily = analysis(CandleInterval.D1, "daily")
    four_hour = analysis(CandleInterval.H4, "four-hour")
    async with session_factory() as session:
        repository = HtfStructureRepository(session)
        first_daily = await repository.upsert_analysis(daily)
        first_four_hour = await repository.upsert_analysis(four_hour)
        await session.commit()

    async with session_factory() as session:
        repository = HtfStructureRepository(session)
        persisted_daily_zone = await repository.latest_zone(
            source=CandleSource.BYBIT,
            symbol="BTCUSDT",
            interval=CandleInterval.D1,
        )
        persisted_daily_event = await repository.latest_event(
            source=CandleSource.BYBIT,
            symbol="BTCUSDT",
            interval=CandleInterval.D1,
        )
        _assert_decimal_model_equivalent(
            persisted_daily_zone,
            daily.primary_zone,
            decimal_fields=("low", "high", "strength_score"),
        )
        _assert_decimal_model_equivalent(
            persisted_daily_event,
            daily.events[0],
            decimal_fields=(
                "close_price",
                "zone_low",
                "zone_high",
                "distance_bps",
                "body_fraction",
                "volume_ratio",
            ),
        )

        second_daily = await repository.upsert_analysis(daily)
        second_four_hour = await repository.upsert_analysis(four_hour)
        await session.commit()
        zone_count = await session.scalar(select(func.count()).select_from(SupportZoneRecord))
        event_count = await session.scalar(
            select(func.count()).select_from(StructureEventRecord)
        )

    evidence = await DerivedHigherTimeframeEvidenceProvider(session_factory).load(
        canonical_symbol="BTCUSDT.P",
        market_symbol="BTCUSDT",
    )

    assert first_daily.zones_inserted == 1
    assert first_four_hour.events_inserted == 1
    assert second_daily.zones_unchanged == 1
    assert second_four_hour.events_unchanged == 1
    assert zone_count == 2
    assert event_count == 2
    assert evidence.origin == HigherTimeframeEvidenceOrigin.DERIVED
    assert evidence.daily_damaged is True
    assert evidence.four_hour_damaged is True
    assert evidence.daily_event_id == "event-daily"
    assert evidence.four_hour_event_id == "event-four-hour"

    await engine.dispose()


@pytest.mark.asyncio
async def test_provider_requires_both_daily_and_four_hour_zones():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        await HtfStructureRepository(session).upsert_analysis(
            analysis(CandleInterval.H4, "four-hour")
        )
        await session.commit()

    provider = DerivedHigherTimeframeEvidenceProvider(session_factory)
    with pytest.raises(ValueError, match="Daily and 4H support evidence"):
        await provider.load(
            canonical_symbol="BTCUSDT.P",
            market_symbol="BTCUSDT",
        )

    await engine.dispose()
