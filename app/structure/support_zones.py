from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256

from app.candles.models import CandleInterval, OhlcvCandle
from app.structure.htf_models import SupportZone


BPS = Decimal("10000")


@dataclass(frozen=True)
class SupportZoneRules:
    pivot_left: int = 2
    pivot_right: int = 2
    minimum_touches: int = 2
    minimum_touch_separation: int = 2
    cluster_tolerance_bps: Decimal = Decimal("75")
    zone_padding_bps: Decimal = Decimal("20")
    maximum_zone_width_bps: Decimal = Decimal("180")
    minimum_rejection_bps: Decimal = Decimal("25")
    maximum_zones: int = 5

    def __post_init__(self) -> None:
        if self.pivot_left < 1 or self.pivot_right < 1:
            raise ValueError("pivot windows must be positive")
        if self.minimum_touches < 2:
            raise ValueError("minimum_touches must be at least two")
        if self.minimum_touch_separation < 1:
            raise ValueError("minimum_touch_separation must be positive")
        for value, name in (
            (self.cluster_tolerance_bps, "cluster_tolerance_bps"),
            (self.zone_padding_bps, "zone_padding_bps"),
            (self.maximum_zone_width_bps, "maximum_zone_width_bps"),
            (self.minimum_rejection_bps, "minimum_rejection_bps"),
        ):
            if not value.is_finite() or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        if self.maximum_zones < 1 or self.maximum_zones > 50:
            raise ValueError("maximum_zones must be between 1 and 50")


@dataclass(frozen=True)
class _PivotLow:
    index: int
    candle: OhlcvCandle

    @property
    def price(self) -> Decimal:
        return self.candle.low_price


def derive_support_zones(
    candles: tuple[OhlcvCandle, ...],
    *,
    rules: SupportZoneRules | None = None,
) -> tuple[SupportZone, ...]:
    active_rules = rules or SupportZoneRules()
    _validate_candles(candles)
    pivots = _find_pivots(candles, active_rules)
    clusters = _cluster_pivots(pivots, active_rules)
    zones = [
        zone
        for cluster in clusters
        if (zone := _zone_from_cluster(cluster, candles, active_rules)) is not None
    ]
    zones.sort(
        key=lambda item: (
            item.strength_score,
            item.last_test_at,
            item.high,
            item.zone_id,
        ),
        reverse=True,
    )
    return tuple(zones[: active_rules.maximum_zones])


def _validate_candles(candles: tuple[OhlcvCandle, ...]) -> None:
    if not candles:
        return
    first = candles[0]
    if first.interval not in {CandleInterval.D1, CandleInterval.H4}:
        raise ValueError("support zones require Daily or 4H candles")
    previous = None
    for candle in candles:
        if (
            candle.source != first.source
            or candle.symbol != first.symbol
            or candle.interval != first.interval
        ):
            raise ValueError("candles must share source, symbol, and interval")
        if previous is not None and candle.open_time <= previous:
            raise ValueError("candles must be strictly chronological")
        previous = candle.open_time


def _find_pivots(
    candles: tuple[OhlcvCandle, ...],
    rules: SupportZoneRules,
) -> tuple[_PivotLow, ...]:
    required = rules.pivot_left + rules.pivot_right + 1
    if len(candles) < required:
        return ()

    pivots: list[_PivotLow] = []
    start = rules.pivot_left
    stop = len(candles) - rules.pivot_right
    for index in range(start, stop):
        current = candles[index]
        left = candles[index - rules.pivot_left : index]
        right = candles[index + 1 : index + 1 + rules.pivot_right]
        left_min = min(item.low_price for item in left)
        right_min = min(item.low_price for item in right)
        is_lowest = current.low_price <= left_min and current.low_price <= right_min
        has_strict_side = current.low_price < left_min or current.low_price < right_min
        if not (is_lowest and has_strict_side):
            continue
        if pivots and index - pivots[-1].index < rules.minimum_touch_separation:
            if current.low_price < pivots[-1].price:
                pivots[-1] = _PivotLow(index=index, candle=current)
            continue
        pivots.append(_PivotLow(index=index, candle=current))
    return tuple(pivots)


def _cluster_pivots(
    pivots: tuple[_PivotLow, ...],
    rules: SupportZoneRules,
) -> tuple[tuple[_PivotLow, ...], ...]:
    if not pivots:
        return ()
    ordered = sorted(pivots, key=lambda item: (item.price, item.candle.open_time))
    clusters: list[list[_PivotLow]] = []
    for pivot in ordered:
        if not clusters:
            clusters.append([pivot])
            continue
        reference = _median_price(clusters[-1])
        distance_bps = abs(pivot.price - reference) / reference * BPS
        if distance_bps <= rules.cluster_tolerance_bps:
            clusters[-1].append(pivot)
        else:
            clusters.append([pivot])
    return tuple(tuple(cluster) for cluster in clusters)


def _median_price(cluster: list[_PivotLow]) -> Decimal:
    prices = sorted(item.price for item in cluster)
    middle = len(prices) // 2
    if len(prices) % 2:
        return prices[middle]
    return (prices[middle - 1] + prices[middle]) / Decimal("2")


def _zone_from_cluster(
    cluster: tuple[_PivotLow, ...],
    candles: tuple[OhlcvCandle, ...],
    rules: SupportZoneRules,
) -> SupportZone | None:
    if len(cluster) < rules.minimum_touches:
        return None
    ordered = tuple(sorted(cluster, key=lambda item: item.candle.open_time))
    core_low = min(item.price for item in ordered)
    core_high = max(item.price for item in ordered)
    padding = rules.zone_padding_bps / BPS
    zone_low = core_low * (Decimal("1") - padding)
    zone_high = core_high * (Decimal("1") + padding)
    midpoint = (zone_low + zone_high) / Decimal("2")
    width_bps = (zone_high - zone_low) / midpoint * BPS
    if width_bps > rules.maximum_zone_width_bps:
        return None

    rejections = sum(
        1
        for item in ordered
        if (item.candle.close_price - item.price) / item.price * BPS
        >= rules.minimum_rejection_bps
    )
    recency = Decimal(ordered[-1].index + 1) / Decimal(len(candles))
    strength = min(
        Decimal("100"),
        Decimal("25")
        + Decimal(len(ordered) * 12)
        + Decimal(rejections * 6)
        + recency * Decimal("15"),
    ).quantize(Decimal("0.01"))
    evidence = tuple(item.candle.open_time for item in ordered)
    zone_id = _zone_id(
        source=ordered[0].candle.source.value,
        symbol=ordered[0].candle.symbol,
        interval=ordered[0].candle.interval.value,
        evidence=evidence,
        low=zone_low,
        high=zone_high,
    )
    reasons = (
        f"TOUCHES_{len(ordered)}",
        f"REJECTIONS_{rejections}",
        f"WIDTH_BPS_{width_bps.quantize(Decimal('0.01'))}",
    )
    return SupportZone(
        zone_id=zone_id,
        source=ordered[0].candle.source,
        symbol=ordered[0].candle.symbol,
        interval=ordered[0].candle.interval,
        low=zone_low,
        high=zone_high,
        created_at=ordered[0].candle.close_time,
        confirmed_at=ordered[-1].candle.close_time,
        last_test_at=ordered[-1].candle.close_time,
        touch_count=len(ordered),
        rejection_count=rejections,
        strength_score=strength,
        evidence_open_times=evidence,
        reasons=reasons,
    )


def _zone_id(
    *,
    source: str,
    symbol: str,
    interval: str,
    evidence: tuple,
    low: Decimal,
    high: Decimal,
) -> str:
    raw = "|".join(
        (
            source,
            symbol,
            interval,
            str(low),
            str(high),
            *(item.isoformat() for item in evidence),
        )
    )
    return f"zone_{sha256(raw.encode('utf-8')).hexdigest()[:24]}"
