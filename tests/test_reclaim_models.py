from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.candles.models import CandleInterval, CandleSource
from app.setups.reclaim_models import (
    DerivedSetupType,
    ReclaimAttempt,
    ReclaimOutcome,
    ReclaimRules,
    SetupReadiness,
)


NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


def failed_pullback() -> ReclaimAttempt:
    return ReclaimAttempt(
        attempt_id="attempt-1",
        break_event_id="break-1",
        zone_id="zone-1",
        source=CandleSource.BYBIT,
        symbol="btcusdt",
        structure_interval=CandleInterval.H4,
        started_at=NOW,
        observed_at=NOW + timedelta(hours=8),
        outcome=ReclaimOutcome.FAILED_PULLBACK,
        setup_type=DerivedSetupType.FAILED_PULLBACK_SHORT,
        readiness=SetupReadiness.QUALIFIED,
        zone_low=Decimal("100"),
        zone_high=Decimal("101"),
        maximum_price=Decimal("100.6"),
        maximum_penetration_bps=Decimal("60"),
        duration_bars=2,
        closes_above_zone=0,
        bars_above_zone=1,
        bounce_volume_ratio=Decimal("0.72"),
        rejection_candle_open_time=NOW + timedelta(hours=4),
        rejection_low=Decimal("99.7"),
        trigger_candle_open_time=NOW + timedelta(hours=8),
        quality_score=Decimal("84.5"),
        reasons=("REJECTION_CONFIRMED", "REJECTION_LOW_BROKEN"),
    )


def test_default_reclaim_rules_are_valid():
    rules = ReclaimRules()

    assert rules.successful_h4_closes == 1
    assert rules.successful_m15_closes == 2
    assert rules.maximum_bounce_volume_ratio == Decimal("0.85")
    assert rules.maximum_setup_age_bars >= rules.maximum_pullback_bars


def test_rules_reject_invalid_windows_and_thresholds():
    with pytest.raises(ValueError, match="cover the pullback window"):
        ReclaimRules(maximum_pullback_bars=12, maximum_setup_age_bars=8)

    with pytest.raises(ValueError, match="must not exceed one"):
        ReclaimRules(minimum_rejection_body_fraction=Decimal("1.01"))

    with pytest.raises(ValueError, match="unreasonably large"):
        ReclaimRules(maximum_bounce_volume_ratio=Decimal("11"))


def test_failed_pullback_contract_normalizes_symbol_and_preserves_evidence():
    attempt = failed_pullback()

    assert attempt.symbol == "BTCUSDT"
    assert attempt.setup_type == DerivedSetupType.FAILED_PULLBACK_SHORT
    assert attempt.readiness == SetupReadiness.QUALIFIED
    assert attempt.rejection_low == Decimal("99.7")
    assert attempt.trigger_candle_open_time is not None


def test_successful_reclaim_must_cancel_short_setup():
    with pytest.raises(ValueError, match="must cancel"):
        ReclaimAttempt(
            attempt_id="attempt-2",
            break_event_id="break-1",
            zone_id="zone-1",
            source=CandleSource.BYBIT,
            symbol="BTCUSDT",
            structure_interval=CandleInterval.H4,
            started_at=NOW,
            observed_at=NOW + timedelta(hours=4),
            outcome=ReclaimOutcome.SUCCESSFUL_RECLAIM,
            setup_type=DerivedSetupType.NONE,
            readiness=SetupReadiness.WATCH,
            zone_low=Decimal("100"),
            zone_high=Decimal("101"),
            maximum_price=Decimal("101.2"),
            maximum_penetration_bps=Decimal("120"),
            duration_bars=1,
            closes_above_zone=1,
            bars_above_zone=1,
            bounce_volume_ratio=Decimal("1.1"),
        )


def test_successful_reclaim_cannot_keep_short_setup_type():
    with pytest.raises(ValueError, match="cannot retain"):
        ReclaimAttempt(
            attempt_id="attempt-2",
            break_event_id="break-1",
            zone_id="zone-1",
            source=CandleSource.BYBIT,
            symbol="BTCUSDT",
            structure_interval=CandleInterval.H4,
            started_at=NOW,
            observed_at=NOW + timedelta(hours=4),
            outcome=ReclaimOutcome.SUCCESSFUL_RECLAIM,
            setup_type=DerivedSetupType.BREAKDOWN_SHORT,
            readiness=SetupReadiness.CANCELLED,
            zone_low=Decimal("100"),
            zone_high=Decimal("101"),
            maximum_price=Decimal("101.2"),
            maximum_penetration_bps=Decimal("120"),
            duration_bars=1,
            closes_above_zone=1,
            bars_above_zone=1,
            bounce_volume_ratio=Decimal("1.1"),
        )


def test_failed_pullback_requires_rejection_and_trigger_evidence():
    base = failed_pullback()
    values = vars(base).copy()
    values["trigger_candle_open_time"] = None

    with pytest.raises(ValueError, match="requires rejection and trigger"):
        ReclaimAttempt(**values)


def test_trigger_must_follow_rejection_candle():
    base = failed_pullback()
    values = vars(base).copy()
    values["trigger_candle_open_time"] = values["rejection_candle_open_time"]

    with pytest.raises(ValueError, match="must follow"):
        ReclaimAttempt(**values)


def test_closes_above_zone_cannot_exceed_bars_above_zone():
    base = failed_pullback()
    values = vars(base).copy()
    values["closes_above_zone"] = 2
    values["bars_above_zone"] = 1

    with pytest.raises(ValueError, match="cannot exceed"):
        ReclaimAttempt(**values)


def test_qualified_evidence_requires_setup_type():
    base = failed_pullback()
    values = vars(base).copy()
    values["outcome"] = ReclaimOutcome.FAILED_RECLAIM
    values["setup_type"] = DerivedSetupType.NONE

    with pytest.raises(ValueError, match="requires a setup type"):
        ReclaimAttempt(**values)


def test_daily_or_four_hour_structure_is_required():
    base = failed_pullback()
    values = vars(base).copy()
    values["structure_interval"] = CandleInterval.M15

    with pytest.raises(ValueError, match="Daily or 4H"):
        ReclaimAttempt(**values)
