from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.candles.models import (
    CandleBatch,
    CandleInterval,
    CandleRole,
    CandleSource,
    OhlcvCandle,
)
from app.structure.htf_engine import analyze_higher_timeframe
from app.structure.htf_models import (
    StructureEventState,
    TimeframeStructureStatus,
)
from app.structure.structure_events import StructureEventRules, build_structure_events
from app.structure.support_zones import SupportZoneRules, derive_support_zones


START = datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc)


def candle(
    index: int,
    *,
    interval: CandleInterval = CandleInterval.H4,
    open_price: str,
    high: str,
    low: str,
    close: str,
    volume: str = "100",
) -> OhlcvCandle:
    open_time = START + index * interval.duration
    return OhlcvCandle(
        source=CandleSource.BYBIT,
        role=CandleRole.STRUCTURE_DATA,
        category="linear",
        symbol="BTCUSDT",
        interval=interval,
        open_time=open_time,
        close_time=open_time + interval.duration,
        open_price=Decimal(open_price),
        high_price=Decimal(high),
        low_price=Decimal(low),
        close_price=Decimal(close),
        volume=Decimal(volume),
        turnover=Decimal(volume) * Decimal(close),
    )


def base_candles(
    *,
    interval: CandleInterval = CandleInterval.H4,
) -> tuple[OhlcvCandle, ...]:
    return (
        candle(0, interval=interval, open_price="103", high="104", low="102", close="103"),
        candle(1, interval=interval, open_price="102", high="104", low="100", close="103"),
        candle(2, interval=interval, open_price="103", high="105", low="103", close="104"),
        candle(
            3,
            interval=interval,
            open_price="102",
            high="104",
            low="100.2",
            close="103",
        ),
        candle(4, interval=interval, open_price="103", high="105", low="103", close="104"),
        candle(5, interval=interval, open_price="103", high="104", low="101", close="102"),
    )


def zone_rules() -> SupportZoneRules:
    return SupportZoneRules(
        pivot_left=1,
        pivot_right=1,
        minimum_touches=2,
        minimum_touch_separation=2,
        cluster_tolerance_bps=Decimal("75"),
        zone_padding_bps=Decimal("20"),
    )


def batch(items: tuple[OhlcvCandle, ...]) -> CandleBatch:
    return CandleBatch(
        source=CandleSource.BYBIT,
        role=CandleRole.STRUCTURE_DATA,
        category="linear",
        symbol="BTCUSDT",
        interval=items[0].interval,
        fetched_at=items[-1].close_time,
        candles=items,
    )


@pytest.mark.parametrize("interval", [CandleInterval.H4, CandleInterval.D1])
def test_support_zone_is_deterministic_and_confirmed_without_lookahead(interval):
    items = base_candles(interval=interval)

    first = derive_support_zones(items, rules=zone_rules())
    second = derive_support_zones(items, rules=zone_rules())

    assert first == second
    assert len(first) == 1
    zone = first[0]
    assert zone.touch_count == 2
    assert zone.evidence_open_times == (items[1].open_time, items[3].open_time)
    assert zone.confirmed_at == items[4].close_time
    assert zone.last_test_at == items[3].close_time
    assert zone.low < Decimal("100") < zone.high
    assert zone.zone_id.startswith("zone_")


def test_confirmed_break_creates_damaged_evidence():
    items = base_candles() + (
        candle(6, open_price="101", high="102", low="97", close="98", volume="180"),
    )
    analysis = analyze_higher_timeframe(
        batch(items),
        support_rules=zone_rules(),
    )

    assert analysis.primary_zone is not None
    assert [event.state for event in analysis.events] == [
        StructureEventState.CONFIRMED_BREAK
    ]
    assert analysis.evidence.status == TimeframeStructureStatus.DAMAGED
    assert analysis.evidence.event_id == analysis.events[0].event_id
    assert analysis.events[0].body_fraction >= Decimal("0.45")
    assert analysis.events[0].distance_bps > 0


def test_weak_close_below_zone_remains_pending():
    items = base_candles() + (
        candle(6, open_price="100", high="101", low="99", close="99.7"),
    )
    zones = derive_support_zones(items, rules=zone_rules())

    events = build_structure_events(zones[0], items)

    assert [event.state for event in events] == [StructureEventState.PENDING_BREAK]


def test_fast_reclaim_marks_fake_break_and_invalidates_break_event():
    items = base_candles() + (
        candle(6, open_price="101", high="102", low="97", close="98", volume="180"),
        candle(7, open_price="99", high="102", low="98", close="101", volume="160"),
    )
    analysis = analyze_higher_timeframe(
        batch(items),
        support_rules=zone_rules(),
    )

    assert [event.state for event in analysis.events] == [
        StructureEventState.CONFIRMED_BREAK,
        StructureEventState.FAKE_BREAK,
    ]
    assert analysis.events[-1].invalidates_event_id == analysis.events[0].event_id
    assert analysis.evidence.status == TimeframeStructureStatus.RECLAIMED


def test_late_reclaim_is_not_classified_as_fake_break():
    items = base_candles() + (
        candle(6, open_price="101", high="102", low="97", close="98", volume="180"),
        candle(7, open_price="99", high="100", low="97", close="98"),
        candle(8, open_price="99", high="100", low="97", close="98"),
        candle(9, open_price="99", high="100", low="97", close="98"),
        candle(10, open_price="99", high="102", low="98", close="101"),
    )
    analysis = analyze_higher_timeframe(
        batch(items),
        support_rules=zone_rules(),
        event_rules=StructureEventRules(fake_break_max_bars=3),
    )

    assert analysis.events[-1].state == StructureEventState.RECLAIMED
    assert analysis.evidence.status == TimeframeStructureStatus.RECLAIMED


def test_insufficient_history_produces_explicit_evidence():
    items = (
        candle(0, open_price="100", high="101", low="99", close="100"),
        candle(1, open_price="100", high="101", low="99", close="100"),
    )

    analysis = analyze_higher_timeframe(batch(items), support_rules=zone_rules())

    assert analysis.zones == ()
    assert analysis.events == ()
    assert analysis.evidence.status == TimeframeStructureStatus.INSUFFICIENT
    assert analysis.evidence.reasons == ("NO_VALID_SUPPORT_ZONE",)


def test_rules_reject_invalid_thresholds():
    with pytest.raises(ValueError):
        SupportZoneRules(pivot_left=0)
    with pytest.raises(ValueError):
        SupportZoneRules(minimum_touches=1)
    with pytest.raises(ValueError):
        StructureEventRules(minimum_break_body_fraction=Decimal("1.1"))
    with pytest.raises(ValueError):
        StructureEventRules(fake_break_max_bars=0)
