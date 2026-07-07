from datetime import datetime
from decimal import Decimal
from hashlib import sha256

from app.candles.models import CandleInterval, OhlcvCandle
from app.setups.reclaim_models import (
    DerivedSetupType,
    ReclaimAttempt,
    ReclaimOutcome,
    ReclaimRules,
    SetupReadiness,
)
from app.structure.htf_models import StructureEvent, StructureEventState, SupportZone


BPS = Decimal("10000")


def analyze_reclaim_attempt(
    *,
    zone: SupportZone,
    break_event: StructureEvent,
    break_candle: OhlcvCandle,
    candles: tuple[OhlcvCandle, ...],
    rules: ReclaimRules | None = None,
) -> ReclaimAttempt:
    """Derive one deterministic post-break reclaim/setup state.

    ``candles`` is the closed post-break confirmation stream. It may be 4H or
    15m, but every candle must share source, symbol, and interval. The break
    candle is supplied separately so bounce-volume quality never needs a
    fabricated baseline.
    """

    active_rules = rules or ReclaimRules()
    _validate_inputs(zone, break_event, break_candle, candles)
    relevant = tuple(candle for candle in candles if candle.close_time > break_event.observed_at)

    if not relevant:
        return _result(
            zone=zone,
            break_event=break_event,
            evaluation_interval=CandleInterval.H4,
            started_at=break_event.observed_at,
            observed_at=break_event.observed_at,
            outcome=ReclaimOutcome.NO_ATTEMPT,
            setup_type=DerivedSetupType.BREAKDOWN_SHORT,
            readiness=SetupReadiness.WATCH,
            maximum_price=break_event.close_price,
            maximum_penetration_bps=Decimal("0"),
            duration_bars=0,
            closes_above_zone=0,
            bars_above_zone=0,
            bounce_volume_ratio=None,
            quality_score=Decimal("0"),
            reasons=("NO_POST_BREAK_CONFIRMATION_CANDLES",),
        )

    evaluation_interval = relevant[0].interval
    successful_index = _successful_reclaim_index(relevant, zone, active_rules)
    if successful_index is not None:
        considered = relevant[: successful_index + 1]
        maximum_price = max(item.high_price for item in considered)
        penetration = _penetration_bps(maximum_price, zone.low)
        closes_above = sum(item.close_price > zone.high for item in considered)
        bars_above = sum(item.high_price > zone.high for item in considered)
        return _result(
            zone=zone,
            break_event=break_event,
            evaluation_interval=evaluation_interval,
            started_at=considered[0].open_time,
            observed_at=considered[-1].close_time,
            outcome=ReclaimOutcome.SUCCESSFUL_RECLAIM,
            setup_type=DerivedSetupType.NONE,
            readiness=SetupReadiness.CANCELLED,
            maximum_price=maximum_price,
            maximum_penetration_bps=penetration,
            duration_bars=len(considered),
            closes_above_zone=closes_above,
            bars_above_zone=bars_above,
            bounce_volume_ratio=_volume_ratio(considered, break_candle.volume),
            quality_score=Decimal("0"),
            reasons=(
                "SUCCESSFUL_RECLAIM_CONFIRMED",
                f"CONFIRMATION_INTERVAL_{evaluation_interval.label.upper()}",
                "SHORT_SETUP_CANCELLED",
            ),
        )

    attempt_index = _first_attempt_index(relevant, zone, active_rules)
    if attempt_index is None:
        continuation = _continuation_result(
            zone=zone,
            break_event=break_event,
            break_candle=break_candle,
            candles=relevant,
            rules=active_rules,
        )
        if continuation is not None:
            return continuation
        if len(relevant) >= active_rules.maximum_setup_age_bars:
            return _result(
                zone=zone,
                break_event=break_event,
                evaluation_interval=evaluation_interval,
                started_at=relevant[0].open_time,
                observed_at=relevant[-1].close_time,
                outcome=ReclaimOutcome.EXPIRED,
                setup_type=DerivedSetupType.NONE,
                readiness=SetupReadiness.EXPIRED,
                maximum_price=max(item.high_price for item in relevant),
                maximum_penetration_bps=Decimal("0"),
                duration_bars=len(relevant),
                closes_above_zone=0,
                bars_above_zone=0,
                bounce_volume_ratio=_volume_ratio(relevant, break_candle.volume),
                quality_score=Decimal("0"),
                reasons=("SETUP_EXPIRED_WITHOUT_RECLAIM_ATTEMPT",),
            )
        return _result(
            zone=zone,
            break_event=break_event,
            evaluation_interval=evaluation_interval,
            started_at=relevant[0].open_time,
            observed_at=relevant[-1].close_time,
            outcome=ReclaimOutcome.NO_ATTEMPT,
            setup_type=DerivedSetupType.BREAKDOWN_SHORT,
            readiness=SetupReadiness.WATCH,
            maximum_price=max(item.high_price for item in relevant),
            maximum_penetration_bps=Decimal("0"),
            duration_bars=len(relevant),
            closes_above_zone=0,
            bars_above_zone=0,
            bounce_volume_ratio=_volume_ratio(relevant, break_candle.volume),
            quality_score=Decimal("0"),
            reasons=("BROKEN_ZONE_NOT_RETESTED",),
        )

    attempt_stream = relevant[attempt_index:]
    limited = attempt_stream[: active_rules.maximum_pullback_bars]
    rejection_index = _rejection_index(limited, zone, active_rules)
    considered = limited if rejection_index is None else limited[: rejection_index + 1]
    maximum_price = max(item.high_price for item in considered)
    penetration = _penetration_bps(maximum_price, zone.low)
    closes_above = sum(item.close_price > zone.high for item in considered)
    bars_above = sum(item.high_price > zone.high for item in considered)
    bounce_volume_ratio = _volume_ratio(considered, break_candle.volume)

    if rejection_index is None:
        if len(attempt_stream) > active_rules.maximum_pullback_bars:
            return _result(
                zone=zone,
                break_event=break_event,
                evaluation_interval=evaluation_interval,
                started_at=attempt_stream[0].open_time,
                observed_at=limited[-1].close_time,
                outcome=ReclaimOutcome.INVALIDATED,
                setup_type=DerivedSetupType.NONE,
                readiness=SetupReadiness.INVALIDATED,
                maximum_price=maximum_price,
                maximum_penetration_bps=penetration,
                duration_bars=len(limited),
                closes_above_zone=closes_above,
                bars_above_zone=bars_above,
                bounce_volume_ratio=bounce_volume_ratio,
                quality_score=Decimal("0"),
                reasons=("PULLBACK_WINDOW_EXCEEDED_WITHOUT_REJECTION",),
            )
        return _result(
            zone=zone,
            break_event=break_event,
            evaluation_interval=evaluation_interval,
            started_at=attempt_stream[0].open_time,
            observed_at=attempt_stream[-1].close_time,
            outcome=ReclaimOutcome.ATTEMPTING,
            setup_type=DerivedSetupType.BREAKDOWN_SHORT,
            readiness=SetupReadiness.WATCH,
            maximum_price=max(item.high_price for item in attempt_stream),
            maximum_penetration_bps=_penetration_bps(
                max(item.high_price for item in attempt_stream),
                zone.low,
            ),
            duration_bars=len(attempt_stream),
            closes_above_zone=sum(item.close_price > zone.high for item in attempt_stream),
            bars_above_zone=sum(item.high_price > zone.high for item in attempt_stream),
            bounce_volume_ratio=_volume_ratio(attempt_stream, break_candle.volume),
            quality_score=Decimal("0"),
            reasons=("RECLAIM_ATTEMPT_IN_PROGRESS",),
        )

    rejection = limited[rejection_index]
    trigger = next(
        (
            candle
            for candle in attempt_stream[rejection_index + 1 :]
            if candle.close_price < rejection.low_price
        ),
        None,
    )
    quality, quality_reasons, warnings = _quality(
        penetration_bps=penetration,
        rejection_body_fraction=_body_fraction(rejection),
        bounce_volume_ratio=bounce_volume_ratio,
        duration_bars=rejection_index + 1,
        rules=active_rules,
        triggered=trigger is not None,
    )

    if trigger is None:
        return _result(
            zone=zone,
            break_event=break_event,
            evaluation_interval=evaluation_interval,
            started_at=attempt_stream[0].open_time,
            observed_at=rejection.close_time,
            outcome=ReclaimOutcome.FAILED_RECLAIM,
            setup_type=DerivedSetupType.BREAKDOWN_SHORT,
            readiness=SetupReadiness.WATCH,
            maximum_price=maximum_price,
            maximum_penetration_bps=penetration,
            duration_bars=rejection_index + 1,
            closes_above_zone=closes_above,
            bars_above_zone=bars_above,
            bounce_volume_ratio=bounce_volume_ratio,
            rejection_candle_open_time=rejection.open_time,
            rejection_low=rejection.low_price,
            quality_score=quality,
            reasons=("RECLAIM_REJECTED", "WAITING_FOR_REJECTION_LOW_BREAK")
            + quality_reasons,
            warnings=warnings,
        )

    return _result(
        zone=zone,
        break_event=break_event,
        evaluation_interval=evaluation_interval,
        started_at=attempt_stream[0].open_time,
        observed_at=trigger.close_time,
        outcome=ReclaimOutcome.FAILED_PULLBACK,
        setup_type=DerivedSetupType.FAILED_PULLBACK_SHORT,
        readiness=SetupReadiness.QUALIFIED,
        maximum_price=maximum_price,
        maximum_penetration_bps=penetration,
        duration_bars=rejection_index + 1,
        closes_above_zone=closes_above,
        bars_above_zone=bars_above,
        bounce_volume_ratio=bounce_volume_ratio,
        rejection_candle_open_time=rejection.open_time,
        rejection_low=rejection.low_price,
        trigger_candle_open_time=trigger.open_time,
        quality_score=quality,
        reasons=(
            "RECLAIM_REJECTED",
            "REJECTION_LOW_BROKEN_ON_CLOSED_CANDLE",
            "FAILED_PULLBACK_PRIMARY_SETUP",
        )
        + quality_reasons,
        warnings=warnings,
    )


def _validate_inputs(
    zone: SupportZone,
    break_event: StructureEvent,
    break_candle: OhlcvCandle,
    candles: tuple[OhlcvCandle, ...],
) -> None:
    if break_event.state != StructureEventState.CONFIRMED_BREAK:
        raise ValueError("reclaim analysis requires a confirmed structure break")
    if break_event.zone_id != zone.zone_id:
        raise ValueError("break event does not belong to support zone")
    if (
        break_event.source != zone.source
        or break_event.symbol != zone.symbol
        or break_event.interval != zone.interval
    ):
        raise ValueError("break event does not match support zone")
    if (
        break_candle.source != zone.source
        or break_candle.symbol != zone.symbol
        or break_candle.interval != zone.interval
        or break_candle.open_time != break_event.candle_open_time
    ):
        raise ValueError("break candle does not match confirmed break event")
    if break_candle.close_time != break_event.observed_at:
        raise ValueError("break candle close must match break observation time")

    previous: datetime | None = None
    interval: CandleInterval | None = None
    for candle in candles:
        if candle.source != zone.source or candle.symbol != zone.symbol:
            raise ValueError("confirmation candle does not match zone source and symbol")
        if candle.interval not in {CandleInterval.H4, CandleInterval.M15}:
            raise ValueError("reclaim confirmation requires 4H or 15m candles")
        if interval is None:
            interval = candle.interval
        elif candle.interval != interval:
            raise ValueError("confirmation candles must share one interval")
        if previous is not None and candle.open_time <= previous:
            raise ValueError("confirmation candles must be strictly chronological")
        previous = candle.open_time


def _successful_reclaim_index(
    candles: tuple[OhlcvCandle, ...],
    zone: SupportZone,
    rules: ReclaimRules,
) -> int | None:
    interval = candles[0].interval
    required = (
        rules.successful_h4_closes
        if interval == CandleInterval.H4
        else rules.successful_m15_closes
    )
    consecutive = 0
    for index, candle in enumerate(candles):
        if candle.close_price > zone.high:
            consecutive += 1
            if consecutive >= required:
                return index
        else:
            consecutive = 0
    return None


def _first_attempt_index(
    candles: tuple[OhlcvCandle, ...],
    zone: SupportZone,
    rules: ReclaimRules,
) -> int | None:
    threshold = zone.low * (
        Decimal("1") + rules.minimum_attempt_penetration_bps / BPS
    )
    return next(
        (index for index, candle in enumerate(candles) if candle.high_price >= threshold),
        None,
    )


def _rejection_index(
    candles: tuple[OhlcvCandle, ...],
    zone: SupportZone,
    rules: ReclaimRules,
) -> int | None:
    for index, candle in enumerate(candles):
        if candle.high_price < zone.low:
            continue
        if candle.close_price >= zone.low or candle.close_price >= candle.open_price:
            continue
        body_fraction = _body_fraction(candle)
        rejection_distance = (zone.low - candle.close_price) / zone.low * BPS
        penetration = _penetration_bps(candle.high_price, zone.low)
        if (
            body_fraction >= rules.minimum_rejection_body_fraction
            and rejection_distance >= rules.minimum_rejection_distance_bps
            and penetration <= rules.maximum_failed_reclaim_penetration_bps
        ):
            return index
    return None


def _continuation_result(
    *,
    zone: SupportZone,
    break_event: StructureEvent,
    break_candle: OhlcvCandle,
    candles: tuple[OhlcvCandle, ...],
    rules: ReclaimRules,
) -> ReclaimAttempt | None:
    if len(candles) < rules.continuation_minimum_bars:
        return None
    search = candles[: rules.maximum_pullback_bars]
    bounce_index = max(range(len(search)), key=lambda index: search[index].high_price)
    if bounce_index == 0 or bounce_index >= len(search) - 1:
        return None
    bounce = search[bounce_index]
    if bounce.high_price >= zone.low or bounce.high_price <= break_event.close_price:
        return None
    trigger = next(
        (
            candle
            for candle in search[bounce_index + 1 :]
            if candle.close_price < break_candle.low_price
            and candle.high_price < bounce.high_price
        ),
        None,
    )
    if trigger is None:
        return None
    considered = search[: search.index(trigger) + 1]
    ratio = _volume_ratio(considered, break_candle.volume)
    warnings = ()
    if ratio is not None and ratio > rules.maximum_bounce_volume_ratio:
        warnings = ("CONTINUATION_BOUNCE_VOLUME_NOT_WEAK",)
    quality = Decimal("65")
    if ratio is not None and ratio <= rules.maximum_bounce_volume_ratio:
        quality += Decimal("10")
    quality -= min(Decimal(len(considered)), Decimal("10"))
    quality = max(Decimal("0"), quality).quantize(Decimal("0.01"))
    return _result(
        zone=zone,
        break_event=break_event,
        evaluation_interval=search[0].interval,
        started_at=search[0].open_time,
        observed_at=trigger.close_time,
        outcome=ReclaimOutcome.CONTINUATION,
        setup_type=DerivedSetupType.CONTINUATION_SHORT,
        readiness=SetupReadiness.QUALIFIED,
        maximum_price=max(item.high_price for item in considered),
        maximum_penetration_bps=Decimal("0"),
        duration_bars=len(considered),
        closes_above_zone=0,
        bars_above_zone=0,
        bounce_volume_ratio=ratio,
        rejection_candle_open_time=bounce.open_time,
        rejection_low=break_candle.low_price,
        trigger_candle_open_time=trigger.open_time,
        quality_score=quality,
        reasons=(
            "LOWER_HIGH_BELOW_BROKEN_ZONE",
            "POST_BOUNCE_LOWER_LOW_CONFIRMED",
            "CONTINUATION_SETUP_SECONDARY",
        ),
        warnings=warnings,
    )


def _quality(
    *,
    penetration_bps: Decimal,
    rejection_body_fraction: Decimal,
    bounce_volume_ratio: Decimal | None,
    duration_bars: int,
    rules: ReclaimRules,
    triggered: bool,
) -> tuple[Decimal, tuple[str, ...], tuple[str, ...]]:
    penetration_fraction = min(
        Decimal("1"),
        penetration_bps / max(rules.maximum_failed_reclaim_penetration_bps, Decimal("1")),
    )
    penetration_component = (Decimal("25") * (Decimal("1") - penetration_fraction)).quantize(
        Decimal("0.01")
    )
    rejection_component = (
        Decimal("30") * min(Decimal("1"), rejection_body_fraction)
    ).quantize(Decimal("0.01"))
    duration_component = (
        Decimal("20")
        * (
            Decimal("1")
            - min(Decimal("1"), Decimal(duration_bars) / Decimal(rules.maximum_pullback_bars))
        )
    ).quantize(Decimal("0.01"))

    warnings: list[str] = []
    if bounce_volume_ratio is None:
        volume_component = Decimal("8")
        warnings.append("BOUNCE_VOLUME_RATIO_UNAVAILABLE")
    elif bounce_volume_ratio <= rules.maximum_bounce_volume_ratio:
        volume_component = (
            Decimal("15")
            + Decimal("10")
            * (
                Decimal("1")
                - bounce_volume_ratio / max(rules.maximum_bounce_volume_ratio, Decimal("0.0001"))
            )
        ).quantize(Decimal("0.01"))
    else:
        volume_component = Decimal("0")
        warnings.append("BOUNCE_VOLUME_NOT_WEAK")

    trigger_component = Decimal("20") if triggered else Decimal("0")
    total = min(
        Decimal("100"),
        penetration_component
        + rejection_component
        + duration_component
        + volume_component
        + trigger_component,
    ).quantize(Decimal("0.01"))
    reasons = (
        f"QUALITY_PENETRATION_{penetration_component}",
        f"QUALITY_REJECTION_{rejection_component}",
        f"QUALITY_DURATION_{duration_component}",
        f"QUALITY_VOLUME_{volume_component}",
        f"QUALITY_TRIGGER_{trigger_component}",
    )
    return total, reasons, tuple(warnings)


def _result(
    *,
    zone: SupportZone,
    break_event: StructureEvent,
    evaluation_interval: CandleInterval,
    started_at: datetime,
    observed_at: datetime,
    outcome: ReclaimOutcome,
    setup_type: DerivedSetupType,
    readiness: SetupReadiness,
    maximum_price: Decimal,
    maximum_penetration_bps: Decimal,
    duration_bars: int,
    closes_above_zone: int,
    bars_above_zone: int,
    bounce_volume_ratio: Decimal | None,
    quality_score: Decimal,
    reasons: tuple[str, ...],
    warnings: tuple[str, ...] = (),
    rejection_candle_open_time: datetime | None = None,
    rejection_low: Decimal | None = None,
    trigger_candle_open_time: datetime | None = None,
) -> ReclaimAttempt:
    return ReclaimAttempt(
        attempt_id=_attempt_id(
            break_event.event_id,
            zone.zone_id,
            evaluation_interval,
            started_at,
        ),
        break_event_id=break_event.event_id,
        zone_id=zone.zone_id,
        source=zone.source,
        symbol=zone.symbol,
        structure_interval=zone.interval,
        started_at=started_at,
        observed_at=observed_at,
        outcome=outcome,
        setup_type=setup_type,
        readiness=readiness,
        zone_low=zone.low,
        zone_high=zone.high,
        maximum_price=maximum_price,
        maximum_penetration_bps=maximum_penetration_bps.quantize(Decimal("0.01")),
        duration_bars=duration_bars,
        closes_above_zone=closes_above_zone,
        bars_above_zone=bars_above_zone,
        bounce_volume_ratio=(
            None
            if bounce_volume_ratio is None
            else bounce_volume_ratio.quantize(Decimal("0.0001"))
        ),
        rejection_candle_open_time=rejection_candle_open_time,
        rejection_low=rejection_low,
        trigger_candle_open_time=trigger_candle_open_time,
        quality_score=quality_score,
        reasons=reasons,
        warnings=warnings,
    )


def _attempt_id(
    break_event_id: str,
    zone_id: str,
    interval: CandleInterval,
    started_at: datetime,
) -> str:
    raw = "|".join((break_event_id, zone_id, interval.value, started_at.isoformat()))
    return f"attempt_{sha256(raw.encode('utf-8')).hexdigest()[:24]}"


def _penetration_bps(price: Decimal, zone_low: Decimal) -> Decimal:
    if price <= zone_low:
        return Decimal("0")
    return (price - zone_low) / zone_low * BPS


def _body_fraction(candle: OhlcvCandle) -> Decimal:
    candle_range = candle.high_price - candle.low_price
    if candle_range == 0:
        return Decimal("0")
    return abs(candle.close_price - candle.open_price) / candle_range


def _volume_ratio(
    candles: tuple[OhlcvCandle, ...],
    breakdown_volume: Decimal,
) -> Decimal | None:
    if not candles or breakdown_volume <= 0:
        return None
    average = sum((item.volume for item in candles), Decimal("0")) / Decimal(len(candles))
    return average / breakdown_volume
