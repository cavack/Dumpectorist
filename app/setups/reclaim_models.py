from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from app.candles.models import CandleInterval, CandleSource


class ReclaimOutcome(StrEnum):
    NO_ATTEMPT = "NO_ATTEMPT"
    ATTEMPTING = "ATTEMPTING"
    SUCCESSFUL_RECLAIM = "SUCCESSFUL_RECLAIM"
    FAILED_RECLAIM = "FAILED_RECLAIM"
    FAILED_PULLBACK = "FAILED_PULLBACK"
    CONTINUATION = "CONTINUATION"
    EXPIRED = "EXPIRED"
    INVALIDATED = "INVALIDATED"


class DerivedSetupType(StrEnum):
    NONE = "NONE"
    BREAKDOWN_SHORT = "BREAKDOWN_SHORT"
    FAILED_PULLBACK_SHORT = "FAILED_PULLBACK_SHORT"
    CONTINUATION_SHORT = "CONTINUATION_SHORT"


class SetupReadiness(StrEnum):
    WATCH = "WATCH"
    QUALIFIED = "QUALIFIED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    INVALIDATED = "INVALIDATED"


def _aware(value: datetime, *, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


def _decimal(
    value: Decimal,
    *,
    name: str,
    minimum: Decimal | None = None,
    maximum: Decimal | None = None,
) -> Decimal:
    try:
        normalized = value if isinstance(value, Decimal) else Decimal(str(value))
    except Exception as error:
        raise ValueError(f"{name} must be decimal-compatible") from error
    if not normalized.is_finite():
        raise ValueError(f"{name} must be finite")
    if minimum is not None and normalized < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    if maximum is not None and normalized > maximum:
        raise ValueError(f"{name} must be at most {maximum}")
    return normalized


@dataclass(frozen=True)
class ReclaimRules:
    successful_h4_closes: int = 1
    successful_m15_closes: int = 2
    minimum_attempt_penetration_bps: Decimal = Decimal("5")
    maximum_failed_reclaim_penetration_bps: Decimal = Decimal("100")
    maximum_bounce_volume_ratio: Decimal = Decimal("0.85")
    minimum_rejection_body_fraction: Decimal = Decimal("0.25")
    minimum_rejection_distance_bps: Decimal = Decimal("5")
    maximum_pullback_bars: int = 12
    maximum_setup_age_bars: int = 30
    continuation_minimum_bars: int = 3

    def __post_init__(self) -> None:
        if self.successful_h4_closes < 1:
            raise ValueError("successful_h4_closes must be positive")
        if self.successful_m15_closes < 1:
            raise ValueError("successful_m15_closes must be positive")
        for value, name in (
            (self.minimum_attempt_penetration_bps, "minimum_attempt_penetration_bps"),
            (
                self.maximum_failed_reclaim_penetration_bps,
                "maximum_failed_reclaim_penetration_bps",
            ),
            (self.maximum_bounce_volume_ratio, "maximum_bounce_volume_ratio"),
            (
                self.minimum_rejection_body_fraction,
                "minimum_rejection_body_fraction",
            ),
            (
                self.minimum_rejection_distance_bps,
                "minimum_rejection_distance_bps",
            ),
        ):
            _decimal(value, name=name, minimum=Decimal("0"))
        if self.maximum_bounce_volume_ratio > Decimal("10"):
            raise ValueError("maximum_bounce_volume_ratio is unreasonably large")
        if self.minimum_rejection_body_fraction > Decimal("1"):
            raise ValueError("minimum_rejection_body_fraction must not exceed one")
        if self.maximum_pullback_bars < 1:
            raise ValueError("maximum_pullback_bars must be positive")
        if self.maximum_setup_age_bars < self.maximum_pullback_bars:
            raise ValueError("maximum_setup_age_bars must cover the pullback window")
        if self.continuation_minimum_bars < 2:
            raise ValueError("continuation_minimum_bars must be at least two")


@dataclass(frozen=True)
class ReclaimAttempt:
    attempt_id: str
    break_event_id: str
    zone_id: str
    source: CandleSource
    symbol: str
    structure_interval: CandleInterval
    started_at: datetime
    observed_at: datetime
    outcome: ReclaimOutcome
    setup_type: DerivedSetupType
    readiness: SetupReadiness
    zone_low: Decimal
    zone_high: Decimal
    maximum_price: Decimal
    maximum_penetration_bps: Decimal
    duration_bars: int
    closes_above_zone: int
    bars_above_zone: int
    bounce_volume_ratio: Decimal | None
    rejection_candle_open_time: datetime | None = None
    rejection_low: Decimal | None = None
    trigger_candle_open_time: datetime | None = None
    quality_score: Decimal = Decimal("0")
    reasons: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        attempt_id = self.attempt_id.strip()
        break_event_id = self.break_event_id.strip()
        zone_id = self.zone_id.strip()
        symbol = self.symbol.strip().upper()
        if not attempt_id or not break_event_id or not zone_id or not symbol:
            raise ValueError("attempt, break-event, zone, and symbol identifiers are required")
        if self.structure_interval not in {CandleInterval.D1, CandleInterval.H4}:
            raise ValueError("reclaim attempt requires Daily or 4H structure evidence")

        started_at = _aware(self.started_at, name="started_at")
        observed_at = _aware(self.observed_at, name="observed_at")
        if observed_at < started_at:
            raise ValueError("observed_at must not precede started_at")

        zone_low = _decimal(
            self.zone_low,
            name="zone_low",
            minimum=Decimal("0.000000000000000001"),
        )
        zone_high = _decimal(
            self.zone_high,
            name="zone_high",
            minimum=Decimal("0.000000000000000001"),
        )
        maximum_price = _decimal(
            self.maximum_price,
            name="maximum_price",
            minimum=Decimal("0.000000000000000001"),
        )
        if zone_low >= zone_high:
            raise ValueError("zone_low must be below zone_high")
        maximum_penetration_bps = _decimal(
            self.maximum_penetration_bps,
            name="maximum_penetration_bps",
            minimum=Decimal("0"),
        )
        quality_score = _decimal(
            self.quality_score,
            name="quality_score",
            minimum=Decimal("0"),
            maximum=Decimal("100"),
        )
        bounce_volume_ratio = (
            None
            if self.bounce_volume_ratio is None
            else _decimal(
                self.bounce_volume_ratio,
                name="bounce_volume_ratio",
                minimum=Decimal("0"),
            )
        )
        rejection_low = (
            None
            if self.rejection_low is None
            else _decimal(
                self.rejection_low,
                name="rejection_low",
                minimum=Decimal("0.000000000000000001"),
            )
        )
        rejection_open = (
            None
            if self.rejection_candle_open_time is None
            else _aware(
                self.rejection_candle_open_time,
                name="rejection_candle_open_time",
            )
        )
        trigger_open = (
            None
            if self.trigger_candle_open_time is None
            else _aware(self.trigger_candle_open_time, name="trigger_candle_open_time")
        )

        if self.duration_bars < 0:
            raise ValueError("duration_bars must be non-negative")
        if self.closes_above_zone < 0 or self.bars_above_zone < 0:
            raise ValueError("zone counters must be non-negative")
        if self.closes_above_zone > self.bars_above_zone:
            raise ValueError("closes_above_zone cannot exceed bars_above_zone")
        if (rejection_open is None) != (rejection_low is None):
            raise ValueError("rejection time and low must be provided together")
        if trigger_open is not None and rejection_open is None:
            raise ValueError("trigger evidence requires rejection evidence")
        if trigger_open is not None and trigger_open <= rejection_open:
            raise ValueError("trigger candle must follow the rejection candle")

        if self.outcome == ReclaimOutcome.SUCCESSFUL_RECLAIM:
            if self.readiness != SetupReadiness.CANCELLED:
                raise ValueError("successful reclaim must cancel the short setup")
            if self.setup_type != DerivedSetupType.NONE:
                raise ValueError("successful reclaim cannot retain a short setup type")
        if self.outcome == ReclaimOutcome.FAILED_PULLBACK:
            if self.setup_type != DerivedSetupType.FAILED_PULLBACK_SHORT:
                raise ValueError("failed pullback must map to FAILED_PULLBACK_SHORT")
            if self.readiness != SetupReadiness.QUALIFIED:
                raise ValueError("failed pullback must be qualified")
            if rejection_open is None or trigger_open is None:
                raise ValueError("failed pullback requires rejection and trigger evidence")
        if self.readiness == SetupReadiness.QUALIFIED and self.setup_type == DerivedSetupType.NONE:
            raise ValueError("qualified evidence requires a setup type")
        if self.readiness in {
            SetupReadiness.CANCELLED,
            SetupReadiness.EXPIRED,
            SetupReadiness.INVALIDATED,
        } and self.setup_type != DerivedSetupType.NONE:
            raise ValueError("inactive setup evidence cannot retain a setup type")

        object.__setattr__(self, "attempt_id", attempt_id)
        object.__setattr__(self, "break_event_id", break_event_id)
        object.__setattr__(self, "zone_id", zone_id)
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "started_at", started_at)
        object.__setattr__(self, "observed_at", observed_at)
        object.__setattr__(self, "zone_low", zone_low)
        object.__setattr__(self, "zone_high", zone_high)
        object.__setattr__(self, "maximum_price", maximum_price)
        object.__setattr__(self, "maximum_penetration_bps", maximum_penetration_bps)
        object.__setattr__(self, "bounce_volume_ratio", bounce_volume_ratio)
        object.__setattr__(self, "rejection_candle_open_time", rejection_open)
        object.__setattr__(self, "rejection_low", rejection_low)
        object.__setattr__(self, "trigger_candle_open_time", trigger_open)
        object.__setattr__(self, "quality_score", quality_score)
