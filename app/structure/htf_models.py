from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from app.candles.models import CandleInterval, CandleSource


class SupportZoneState(StrEnum):
    ACTIVE = "ACTIVE"
    BROKEN = "BROKEN"
    RECLAIMED = "RECLAIMED"
    EXPIRED = "EXPIRED"


class StructureEventState(StrEnum):
    PENDING_BREAK = "PENDING_BREAK"
    CONFIRMED_BREAK = "CONFIRMED_BREAK"
    FAKE_BREAK = "FAKE_BREAK"
    RECLAIMED = "RECLAIMED"
    INVALIDATED = "INVALIDATED"


class TimeframeStructureStatus(StrEnum):
    INTACT = "INTACT"
    WATCH = "WATCH"
    DAMAGED = "DAMAGED"
    RECLAIMED = "RECLAIMED"
    INVALIDATED = "INVALIDATED"
    INSUFFICIENT = "INSUFFICIENT"


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


def _htf_interval(interval: CandleInterval) -> CandleInterval:
    if interval not in {CandleInterval.D1, CandleInterval.H4}:
        raise ValueError("higher-timeframe evidence requires Daily or 4H")
    return interval


@dataclass(frozen=True)
class SupportZone:
    zone_id: str
    source: CandleSource
    symbol: str
    interval: CandleInterval
    low: Decimal
    high: Decimal
    created_at: datetime
    confirmed_at: datetime
    last_test_at: datetime
    touch_count: int
    rejection_count: int
    strength_score: Decimal
    evidence_open_times: tuple[datetime, ...]
    state: SupportZoneState = SupportZoneState.ACTIVE
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        zone_id = self.zone_id.strip()
        symbol = self.symbol.strip().upper()
        if not zone_id:
            raise ValueError("zone_id is required")
        if not symbol:
            raise ValueError("symbol is required")
        interval = _htf_interval(self.interval)
        low = _decimal(self.low, name="low", minimum=Decimal("0.000000000000000001"))
        high = _decimal(self.high, name="high", minimum=Decimal("0.000000000000000001"))
        if low >= high:
            raise ValueError("support-zone low must be below high")
        created_at = _aware(self.created_at, name="created_at")
        confirmed_at = _aware(self.confirmed_at, name="confirmed_at")
        last_test_at = _aware(self.last_test_at, name="last_test_at")
        if confirmed_at < created_at:
            raise ValueError("confirmed_at must not precede created_at")
        if last_test_at < created_at:
            raise ValueError("last_test_at must not precede created_at")
        if self.touch_count < 2:
            raise ValueError("support zone requires at least two touches")
        if self.rejection_count < 0 or self.rejection_count > self.touch_count:
            raise ValueError("rejection_count must be between zero and touch_count")
        strength_score = _decimal(
            self.strength_score,
            name="strength_score",
            minimum=Decimal("0"),
            maximum=Decimal("100"),
        )
        evidence = tuple(_aware(item, name="evidence_open_time") for item in self.evidence_open_times)
        if len(evidence) != self.touch_count:
            raise ValueError("touch_count must match evidence_open_times")
        if tuple(sorted(set(evidence))) != evidence:
            raise ValueError("evidence_open_times must be unique and chronological")

        object.__setattr__(self, "zone_id", zone_id)
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "interval", interval)
        object.__setattr__(self, "low", low)
        object.__setattr__(self, "high", high)
        object.__setattr__(self, "created_at", created_at)
        object.__setattr__(self, "confirmed_at", confirmed_at)
        object.__setattr__(self, "last_test_at", last_test_at)
        object.__setattr__(self, "strength_score", strength_score)
        object.__setattr__(self, "evidence_open_times", evidence)

    @property
    def midpoint(self) -> Decimal:
        return (self.low + self.high) / Decimal("2")


@dataclass(frozen=True)
class StructureEvent:
    event_id: str
    zone_id: str
    source: CandleSource
    symbol: str
    interval: CandleInterval
    state: StructureEventState
    observed_at: datetime
    candle_open_time: datetime
    close_price: Decimal
    zone_low: Decimal
    zone_high: Decimal
    distance_bps: Decimal
    body_fraction: Decimal
    volume_ratio: Decimal | None = None
    invalidates_event_id: str | None = None
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        event_id = self.event_id.strip()
        zone_id = self.zone_id.strip()
        symbol = self.symbol.strip().upper()
        if not event_id or not zone_id or not symbol:
            raise ValueError("event_id, zone_id, and symbol are required")
        interval = _htf_interval(self.interval)
        observed_at = _aware(self.observed_at, name="observed_at")
        candle_open_time = _aware(self.candle_open_time, name="candle_open_time")
        if observed_at <= candle_open_time:
            raise ValueError("observed_at must follow candle_open_time")
        close_price = _decimal(
            self.close_price,
            name="close_price",
            minimum=Decimal("0.000000000000000001"),
        )
        zone_low = _decimal(self.zone_low, name="zone_low", minimum=Decimal("0.000000000000000001"))
        zone_high = _decimal(self.zone_high, name="zone_high", minimum=Decimal("0.000000000000000001"))
        if zone_low >= zone_high:
            raise ValueError("zone_low must be below zone_high")
        distance_bps = _decimal(self.distance_bps, name="distance_bps", minimum=Decimal("0"))
        body_fraction = _decimal(
            self.body_fraction,
            name="body_fraction",
            minimum=Decimal("0"),
            maximum=Decimal("1"),
        )
        volume_ratio = (
            None
            if self.volume_ratio is None
            else _decimal(self.volume_ratio, name="volume_ratio", minimum=Decimal("0"))
        )

        object.__setattr__(self, "event_id", event_id)
        object.__setattr__(self, "zone_id", zone_id)
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "interval", interval)
        object.__setattr__(self, "observed_at", observed_at)
        object.__setattr__(self, "candle_open_time", candle_open_time)
        object.__setattr__(self, "close_price", close_price)
        object.__setattr__(self, "zone_low", zone_low)
        object.__setattr__(self, "zone_high", zone_high)
        object.__setattr__(self, "distance_bps", distance_bps)
        object.__setattr__(self, "body_fraction", body_fraction)
        object.__setattr__(self, "volume_ratio", volume_ratio)


@dataclass(frozen=True)
class TimeframeStructureEvidence:
    source: CandleSource
    symbol: str
    interval: CandleInterval
    status: TimeframeStructureStatus
    observed_at: datetime
    zone_id: str | None = None
    event_id: str | None = None
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        symbol = self.symbol.strip().upper()
        if not symbol:
            raise ValueError("symbol is required")
        interval = _htf_interval(self.interval)
        observed_at = _aware(self.observed_at, name="observed_at")
        if self.status == TimeframeStructureStatus.DAMAGED and not self.event_id:
            raise ValueError("damaged evidence requires event_id")
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "interval", interval)
        object.__setattr__(self, "observed_at", observed_at)

    @property
    def damaged(self) -> bool:
        return self.status == TimeframeStructureStatus.DAMAGED


@dataclass(frozen=True)
class HtfStructureAnalysis:
    source: CandleSource
    symbol: str
    interval: CandleInterval
    observed_at: datetime
    zones: tuple[SupportZone, ...]
    primary_zone: SupportZone | None
    events: tuple[StructureEvent, ...]
    evidence: TimeframeStructureEvidence

    def __post_init__(self) -> None:
        symbol = self.symbol.strip().upper()
        interval = _htf_interval(self.interval)
        observed_at = _aware(self.observed_at, name="observed_at")
        if not symbol:
            raise ValueError("symbol is required")
        if self.evidence.symbol != symbol or self.evidence.interval != interval:
            raise ValueError("evidence must match analysis symbol and interval")
        if self.primary_zone is not None and self.primary_zone not in self.zones:
            raise ValueError("primary_zone must be included in zones")
        for zone in self.zones:
            if zone.symbol != symbol or zone.interval != interval or zone.source != self.source:
                raise ValueError("zone does not match analysis")
        for event in self.events:
            if event.symbol != symbol or event.interval != interval or event.source != self.source:
                raise ValueError("event does not match analysis")
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "interval", interval)
        object.__setattr__(self, "observed_at", observed_at)
