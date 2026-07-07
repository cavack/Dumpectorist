from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256

from app.candles.models import OhlcvCandle
from app.structure.htf_models import (
    StructureEvent,
    StructureEventState,
    SupportZone,
    TimeframeStructureEvidence,
    TimeframeStructureStatus,
)


BPS = Decimal("10000")


@dataclass(frozen=True)
class StructureEventRules:
    minimum_break_distance_bps: Decimal = Decimal("10")
    minimum_break_body_fraction: Decimal = Decimal("0.45")
    fake_break_max_bars: int = 3
    maximum_zone_age_bars: int = 100
    volume_lookback: int = 5

    def __post_init__(self) -> None:
        if (
            not self.minimum_break_distance_bps.is_finite()
            or self.minimum_break_distance_bps < 0
        ):
            raise ValueError("minimum_break_distance_bps must be non-negative")
        if (
            not self.minimum_break_body_fraction.is_finite()
            or self.minimum_break_body_fraction < 0
            or self.minimum_break_body_fraction > 1
        ):
            raise ValueError("minimum_break_body_fraction must be between zero and one")
        if self.fake_break_max_bars < 1:
            raise ValueError("fake_break_max_bars must be positive")
        if self.maximum_zone_age_bars < 1:
            raise ValueError("maximum_zone_age_bars must be positive")
        if self.volume_lookback < 1:
            raise ValueError("volume_lookback must be positive")


def build_structure_events(
    zone: SupportZone,
    candles: tuple[OhlcvCandle, ...],
    *,
    rules: StructureEventRules | None = None,
) -> tuple[StructureEvent, ...]:
    active_rules = rules or StructureEventRules()
    _validate_inputs(zone, candles)
    relevant = tuple(item for item in candles if item.open_time >= zone.confirmed_at)
    if not relevant:
        return ()

    events: list[StructureEvent] = []
    confirmed_index: int | None = None
    confirmed_event_id: str | None = None
    pending_emitted = False

    for index, candle in enumerate(relevant):
        body_fraction = _body_fraction(candle)
        volume_ratio = _volume_ratio(relevant, index, active_rules.volume_lookback)
        if confirmed_index is None:
            if candle.close_price < zone.low:
                distance_bps = (zone.low - candle.close_price) / zone.low * BPS
                confirmed = (
                    distance_bps >= active_rules.minimum_break_distance_bps
                    and body_fraction >= active_rules.minimum_break_body_fraction
                )
                if confirmed:
                    event = _event(
                        zone,
                        candle,
                        state=StructureEventState.CONFIRMED_BREAK,
                        distance_bps=distance_bps,
                        body_fraction=body_fraction,
                        volume_ratio=volume_ratio,
                        reasons=(
                            "CLOSE_BELOW_SUPPORT_ZONE",
                            "BREAK_DISTANCE_CONFIRMED",
                            "BREAK_BODY_CONFIRMED",
                        ),
                    )
                    events.append(event)
                    confirmed_index = index
                    confirmed_event_id = event.event_id
                elif not pending_emitted:
                    events.append(
                        _event(
                            zone,
                            candle,
                            state=StructureEventState.PENDING_BREAK,
                            distance_bps=distance_bps,
                            body_fraction=body_fraction,
                            volume_ratio=volume_ratio,
                            reasons=(
                                "CLOSE_BELOW_SUPPORT_ZONE",
                                "BREAK_CONFIRMATION_INCOMPLETE",
                            ),
                        )
                    )
                    pending_emitted = True
            elif index + 1 > active_rules.maximum_zone_age_bars:
                events.append(
                    _event(
                        zone,
                        candle,
                        state=StructureEventState.INVALIDATED,
                        distance_bps=Decimal("0"),
                        body_fraction=body_fraction,
                        volume_ratio=volume_ratio,
                        reasons=("SUPPORT_ZONE_EXPIRED_WITHOUT_BREAK",),
                    )
                )
                break
            continue

        if candle.close_price > zone.high:
            bars_after_break = index - confirmed_index
            state = (
                StructureEventState.FAKE_BREAK
                if bars_after_break <= active_rules.fake_break_max_bars
                else StructureEventState.RECLAIMED
            )
            distance_bps = (candle.close_price - zone.high) / zone.high * BPS
            events.append(
                _event(
                    zone,
                    candle,
                    state=state,
                    distance_bps=distance_bps,
                    body_fraction=body_fraction,
                    volume_ratio=volume_ratio,
                    invalidates_event_id=confirmed_event_id,
                    reasons=(
                        "CLOSE_ABOVE_SUPPORT_ZONE",
                        f"BARS_AFTER_BREAK_{bars_after_break}",
                    ),
                )
            )
            break

    return tuple(events)


def evidence_from_events(
    zone: SupportZone | None,
    events: tuple[StructureEvent, ...],
    *,
    source,
    symbol: str,
    interval,
    observed_at,
) -> TimeframeStructureEvidence:
    if zone is None:
        return TimeframeStructureEvidence(
            source=source,
            symbol=symbol,
            interval=interval,
            status=TimeframeStructureStatus.INSUFFICIENT,
            observed_at=observed_at,
            reasons=("NO_VALID_SUPPORT_ZONE",),
        )
    if not events:
        return TimeframeStructureEvidence(
            source=source,
            symbol=symbol,
            interval=interval,
            status=TimeframeStructureStatus.INTACT,
            observed_at=observed_at,
            zone_id=zone.zone_id,
            reasons=("SUPPORT_ZONE_INTACT",),
        )

    latest = events[-1]
    status_map = {
        StructureEventState.PENDING_BREAK: TimeframeStructureStatus.WATCH,
        StructureEventState.CONFIRMED_BREAK: TimeframeStructureStatus.DAMAGED,
        StructureEventState.FAKE_BREAK: TimeframeStructureStatus.RECLAIMED,
        StructureEventState.RECLAIMED: TimeframeStructureStatus.RECLAIMED,
        StructureEventState.INVALIDATED: TimeframeStructureStatus.INVALIDATED,
    }
    return TimeframeStructureEvidence(
        source=source,
        symbol=symbol,
        interval=interval,
        status=status_map[latest.state],
        observed_at=latest.observed_at,
        zone_id=zone.zone_id,
        event_id=latest.event_id,
        reasons=latest.reasons + (f"EVENT_STATE_{latest.state.value}",),
    )


def _validate_inputs(zone: SupportZone, candles: tuple[OhlcvCandle, ...]) -> None:
    previous = None
    for candle in candles:
        if (
            candle.source != zone.source
            or candle.symbol != zone.symbol
            or candle.interval != zone.interval
        ):
            raise ValueError("candle does not match support zone")
        if previous is not None and candle.open_time <= previous:
            raise ValueError("candles must be strictly chronological")
        previous = candle.open_time


def _body_fraction(candle: OhlcvCandle) -> Decimal:
    candle_range = candle.high_price - candle.low_price
    if candle_range == 0:
        return Decimal("0")
    return (abs(candle.close_price - candle.open_price) / candle_range).quantize(
        Decimal("0.0001")
    )


def _volume_ratio(
    candles: tuple[OhlcvCandle, ...],
    index: int,
    lookback: int,
) -> Decimal | None:
    start = max(0, index - lookback)
    history = candles[start:index]
    if not history:
        return None
    average = sum((item.volume for item in history), Decimal("0")) / Decimal(
        len(history)
    )
    if average == 0:
        return None
    return (candles[index].volume / average).quantize(Decimal("0.0001"))


def _event(
    zone: SupportZone,
    candle: OhlcvCandle,
    *,
    state: StructureEventState,
    distance_bps: Decimal,
    body_fraction: Decimal,
    volume_ratio: Decimal | None,
    reasons: tuple[str, ...],
    invalidates_event_id: str | None = None,
) -> StructureEvent:
    event_id = _event_id(zone.zone_id, candle, state)
    return StructureEvent(
        event_id=event_id,
        zone_id=zone.zone_id,
        source=zone.source,
        symbol=zone.symbol,
        interval=zone.interval,
        state=state,
        observed_at=candle.close_time,
        candle_open_time=candle.open_time,
        close_price=candle.close_price,
        zone_low=zone.low,
        zone_high=zone.high,
        distance_bps=distance_bps.quantize(Decimal("0.01")),
        body_fraction=body_fraction,
        volume_ratio=volume_ratio,
        invalidates_event_id=invalidates_event_id,
        reasons=reasons,
    )


def _event_id(
    zone_id: str,
    candle: OhlcvCandle,
    state: StructureEventState,
) -> str:
    raw = "|".join(
        (
            zone_id,
            candle.open_time.isoformat(),
            candle.close_time.isoformat(),
            state.value,
        )
    )
    return f"event_{sha256(raw.encode('utf-8')).hexdigest()[:24]}"
