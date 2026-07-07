from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.candles.health import (
    CandleFreshnessRules,
    CandleFreshnessState,
    evaluate_candle_freshness,
)
from app.candles.models import (
    CandleBatch,
    CandleInterval,
    CandleRole,
    CandleSource,
    OhlcvCandle,
)
from app.candles.serialization import batch_from_payload_data, batch_to_payload_data


NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


def make_candle(
    *,
    interval: CandleInterval = CandleInterval.H4,
    open_time: datetime | None = None,
    close_price: str = "101",
) -> OhlcvCandle:
    start = open_time or (NOW - interval.duration)
    return OhlcvCandle(
        source=CandleSource.BYBIT,
        role=CandleRole.STRUCTURE_DATA,
        category="linear",
        symbol="BTCUSDT",
        interval=interval,
        open_time=start,
        close_time=start + interval.duration,
        open_price=Decimal("100"),
        high_price=Decimal("102"),
        low_price=Decimal("99"),
        close_price=Decimal(close_price),
        volume=Decimal("10"),
        turnover=Decimal("1005"),
    )


def make_batch(*candles: OhlcvCandle, fetched_at: datetime = NOW) -> CandleBatch:
    return CandleBatch(
        source=CandleSource.BYBIT,
        role=CandleRole.STRUCTURE_DATA,
        category="linear",
        symbol="BTCUSDT",
        interval=candles[0].interval if candles else CandleInterval.H4,
        fetched_at=fetched_at,
        candles=tuple(candles),
    )


@pytest.mark.parametrize(
    "interval",
    [CandleInterval.M5, CandleInterval.M15, CandleInterval.H4, CandleInterval.D1],
)
def test_supported_intervals_create_valid_closed_candles(interval):
    candle = make_candle(interval=interval)

    assert candle.close_time - candle.open_time == interval.duration
    assert candle.symbol == "BTCUSDT"


def test_candle_rejects_naive_time_and_invalid_values():
    with pytest.raises(ValueError):
        make_candle(open_time=datetime(2026, 7, 7, 8, 0))

    with pytest.raises(ValueError):
        OhlcvCandle(
            source=CandleSource.BYBIT,
            role=CandleRole.STRUCTURE_DATA,
            category="linear",
            symbol="BTCUSDT",
            interval=CandleInterval.H4,
            open_time=NOW - timedelta(hours=4),
            close_time=NOW,
            open_price=Decimal("100"),
            high_price=Decimal("99"),
            low_price=Decimal("98"),
            close_price=Decimal("100"),
            volume=Decimal("1"),
            turnover=Decimal("1"),
        )

    with pytest.raises(ValueError):
        make_candle(close_price="NaN")


def test_batch_rejects_open_duplicate_and_non_chronological_candles():
    first = make_candle(open_time=NOW - timedelta(hours=8))
    second = make_candle(open_time=NOW - timedelta(hours=4))

    with pytest.raises(ValueError):
        make_batch(second, first)
    with pytest.raises(ValueError):
        make_batch(first, first)
    with pytest.raises(ValueError):
        make_batch(second, fetched_at=NOW - timedelta(seconds=1))


def test_freshness_reports_ok_empty_stale_and_future():
    latest = make_candle(open_time=NOW - timedelta(hours=4))
    assert evaluate_candle_freshness(make_batch(latest), now=NOW).state == CandleFreshnessState.OK

    empty = CandleBatch(
        source=CandleSource.BYBIT,
        role=CandleRole.STRUCTURE_DATA,
        category="linear",
        symbol="BTCUSDT",
        interval=CandleInterval.H4,
        fetched_at=NOW,
        candles=(),
    )
    assert evaluate_candle_freshness(empty, now=NOW).state == CandleFreshnessState.EMPTY

    old = make_candle(open_time=NOW - timedelta(hours=16))
    assert evaluate_candle_freshness(make_batch(old), now=NOW).state == CandleFreshnessState.STALE

    future_batch = make_batch(latest, fetched_at=NOW + timedelta(seconds=2))
    report = evaluate_candle_freshness(
        future_batch,
        now=NOW - timedelta(seconds=2),
        rules=CandleFreshnessRules(future_tolerance_seconds=1),
    )
    assert report.state == CandleFreshnessState.FUTURE


def test_freshness_rejects_invalid_rules_and_naive_now():
    with pytest.raises(ValueError):
        CandleFreshnessRules(max_age_intervals=0)
    with pytest.raises(ValueError):
        evaluate_candle_freshness(
            make_batch(make_candle()),
            now=datetime(2026, 7, 7, 12, 0),
        )


def test_batch_serialization_round_trip_preserves_decimal_and_time():
    first = make_candle(open_time=NOW - timedelta(hours=8))
    second = make_candle(open_time=NOW - timedelta(hours=4), close_price="100.5")
    batch = make_batch(first, second)

    restored = batch_from_payload_data(batch_to_payload_data(batch))

    assert restored == batch
    assert restored.latest is not None
    assert restored.latest.close_price == Decimal("100.5")
