from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.candles.models import CandleInterval, CandleSource
from app.setups.reclaim_models import (
    DerivedSetupType,
    ReclaimAttempt,
    ReclaimOutcome,
    SetupReadiness,
)

NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


def reclaim_attempt(*, qualified: bool = False) -> ReclaimAttempt:
    return ReclaimAttempt(
        attempt_id="attempt-1",
        break_event_id="break-1",
        zone_id="zone-1",
        source=CandleSource.BYBIT,
        symbol="BTCUSDT",
        structure_interval=CandleInterval.H4,
        started_at=NOW,
        observed_at=NOW + timedelta(hours=8 if qualified else 4),
        outcome=(
            ReclaimOutcome.FAILED_PULLBACK
            if qualified
            else ReclaimOutcome.FAILED_RECLAIM
        ),
        setup_type=(
            DerivedSetupType.FAILED_PULLBACK_SHORT
            if qualified
            else DerivedSetupType.BREAKDOWN_SHORT
        ),
        readiness=SetupReadiness.QUALIFIED if qualified else SetupReadiness.WATCH,
        zone_low=Decimal("100"),
        zone_high=Decimal("101"),
        maximum_price=Decimal("100.6"),
        maximum_penetration_bps=Decimal("60"),
        duration_bars=2,
        closes_above_zone=0,
        bars_above_zone=1,
        bounce_volume_ratio=Decimal("0.72"),
        rejection_candle_open_time=NOW + timedelta(hours=4),
        rejection_low=Decimal("98.8"),
        trigger_candle_open_time=NOW + timedelta(hours=8) if qualified else None,
        quality_score=Decimal("84.5") if qualified else Decimal("54.5"),
        reasons=("RECLAIM_REJECTED",),
    )
