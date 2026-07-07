from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.candles.models import CandleInterval, CandleRole, CandleSource, OhlcvCandle
from app.setups.reclaim_engine import analyze_reclaim_attempt
from app.setups.reclaim_models import DerivedSetupType, ReclaimOutcome, SetupReadiness
from app.structure.htf_models import StructureEvent, StructureEventState, SupportZone

NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


def candle(interval, opened, open_price, high, low, close, volume="600"):
    return OhlcvCandle(
        source=CandleSource.BYBIT,
        role=CandleRole.STRUCTURE_DATA,
        category="linear",
        symbol="BTCUSDT",
        interval=interval,
        open_time=opened,
        close_time=opened + interval.duration,
        open_price=Decimal(open_price),
        high_price=Decimal(high),
        low_price=Decimal(low),
        close_price=Decimal(close),
        volume=Decimal(volume),
        turnover=Decimal(volume) * Decimal(close),
    )


def zone():
    return SupportZone(
        zone_id="zone-1",
        source=CandleSource.BYBIT,
        symbol="BTCUSDT",
        interval=CandleInterval.H4,
        low=Decimal("100"),
        high=Decimal("101"),
        created_at=NOW - timedelta(days=3),
        confirmed_at=NOW - timedelta(days=1),
        last_test_at=NOW - timedelta(hours=8),
        touch_count=2,
        rejection_count=2,
        strength_score=Decimal("80"),
        evidence_open_times=(
            NOW - timedelta(days=3, hours=4),
            NOW - timedelta(days=1, hours=4),
        ),
    )


def broken_candle():
    return candle(CandleInterval.H4, NOW - timedelta(hours=4), "101", "102", "97", "98", "1000")


def broken_event():
    return StructureEvent(
        event_id="break-1",
        zone_id="zone-1",
        source=CandleSource.BYBIT,
        symbol="BTCUSDT",
        interval=CandleInterval.H4,
        state=StructureEventState.CONFIRMED_BREAK,
        observed_at=NOW,
        candle_open_time=NOW - timedelta(hours=4),
        close_price=Decimal("98"),
        zone_low=Decimal("100"),
        zone_high=Decimal("101"),
        distance_bps=Decimal("200"),
        body_fraction=Decimal("0.6"),
        volume_ratio=Decimal("1.5"),
    )


def analyze(items):
    return analyze_reclaim_attempt(
        zone=zone(),
        break_event=broken_event(),
        break_candle=broken_candle(),
        candles=items,
    )


def test_four_hour_close_above_zone_cancels_short_setup():
    result = analyze((candle(CandleInterval.H4, NOW, "99", "101.5", "98.5", "101.2"),))
    assert result.outcome == ReclaimOutcome.SUCCESSFUL_RECLAIM
    assert result.setup_type == DerivedSetupType.NONE
    assert result.readiness == SetupReadiness.CANCELLED
    assert "SHORT_SETUP_CANCELLED" in result.reasons


def test_two_consecutive_fifteen_minute_closes_confirm_reclaim():
    result = analyze(
        (
            candle(CandleInterval.M15, NOW, "100.8", "101.3", "100.6", "101.1"),
            candle(
                CandleInterval.M15,
                NOW + timedelta(minutes=15),
                "101.1",
                "101.5",
                "100.9",
                "101.2",
            ),
        )
    )
    assert result.outcome == ReclaimOutcome.SUCCESSFUL_RECLAIM
    assert result.duration_bars == 2
    assert "CONFIRMATION_INTERVAL_15M" in result.reasons


def test_rejection_then_closed_break_of_low_qualifies_failed_pullback():
    result = analyze(
        (
            candle(CandleInterval.H4, NOW, "98.5", "100.4", "98", "99.5", "600"),
            candle(
                CandleInterval.H4,
                NOW + timedelta(hours=4),
                "100",
                "100.6",
                "98.8",
                "99",
                "550",
            ),
            candle(
                CandleInterval.H4,
                NOW + timedelta(hours=8),
                "99",
                "99.2",
                "98",
                "98.5",
                "500",
            ),
        )
    )
    assert result.outcome == ReclaimOutcome.FAILED_PULLBACK
    assert result.setup_type == DerivedSetupType.FAILED_PULLBACK_SHORT
    assert result.readiness == SetupReadiness.QUALIFIED
    assert result.rejection_low == Decimal("98.8")
    assert result.trigger_candle_open_time == NOW + timedelta(hours=8)
    assert result.quality_score > Decimal("50")


def test_rejection_without_trigger_remains_watch():
    result = analyze(
        (
            candle(CandleInterval.H4, NOW, "99", "100.5", "98.8", "99.6"),
            candle(CandleInterval.H4, NOW + timedelta(hours=4), "100", "100.4", "98.9", "99.1"),
        )
    )
    assert result.outcome == ReclaimOutcome.FAILED_RECLAIM
    assert result.setup_type == DerivedSetupType.BREAKDOWN_SHORT
    assert result.readiness == SetupReadiness.WATCH
    assert result.trigger_candle_open_time is None


def test_weak_bounce_below_zone_then_lower_low_is_continuation():
    result = analyze(
        (
            candle(CandleInterval.H4, NOW, "98", "98.8", "97.8", "98.5", "500"),
            candle(CandleInterval.H4, NOW + timedelta(hours=4), "98.5", "99.4", "98.3", "99", "450"),
            candle(CandleInterval.H4, NOW + timedelta(hours=8), "98.8", "99", "96.5", "96.8", "500"),
        )
    )
    assert result.outcome == ReclaimOutcome.CONTINUATION
    assert result.setup_type == DerivedSetupType.CONTINUATION_SHORT
    assert result.readiness == SetupReadiness.QUALIFIED


def test_setup_expires_without_retest():
    items = tuple(
        candle(
            CandleInterval.M15,
            NOW + timedelta(minutes=15 * index),
            "98",
            "98.5",
            "97.5",
            "98",
            "400",
        )
        for index in range(30)
    )
    result = analyze(items)
    assert result.outcome == ReclaimOutcome.EXPIRED
    assert result.setup_type == DerivedSetupType.NONE
    assert result.readiness == SetupReadiness.EXPIRED


def test_attempt_id_is_deterministic():
    items = (candle(CandleInterval.H4, NOW, "99", "100.2", "98.5", "99.5"),)
    assert analyze(items).attempt_id == analyze(items).attempt_id


def test_non_confirmed_break_is_rejected():
    event = broken_event()
    values = vars(event).copy()
    values["state"] = StructureEventState.PENDING_BREAK
    with pytest.raises(ValueError, match="confirmed structure break"):
        analyze_reclaim_attempt(
            zone=zone(),
            break_event=StructureEvent(**values),
            break_candle=broken_candle(),
            candles=(),
        )
