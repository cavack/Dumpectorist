from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum


class CandleSource(StrEnum):
    BYBIT = "BYBIT"


class CandleRole(StrEnum):
    STRUCTURE_DATA = "STRUCTURE_DATA"


class CandleInterval(StrEnum):
    M5 = "5"
    M15 = "15"
    H4 = "240"
    D1 = "D"

    @property
    def duration(self) -> timedelta:
        return {
            CandleInterval.M5: timedelta(minutes=5),
            CandleInterval.M15: timedelta(minutes=15),
            CandleInterval.H4: timedelta(hours=4),
            CandleInterval.D1: timedelta(days=1),
        }[self]

    @property
    def label(self) -> str:
        return {
            CandleInterval.M5: "5m",
            CandleInterval.M15: "15m",
            CandleInterval.H4: "4h",
            CandleInterval.D1: "1d",
        }[self]


def _decimal(value: Decimal, *, name: str, positive: bool = False) -> Decimal:
    if not isinstance(value, Decimal):
        try:
            value = Decimal(str(value))
        except Exception as error:
            raise ValueError(f"{name} must be decimal-compatible") from error
    if not value.is_finite():
        raise ValueError(f"{name} must be finite")
    if positive and value <= 0:
        raise ValueError(f"{name} must be positive")
    if not positive and value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _aware(value: datetime, *, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


@dataclass(frozen=True)
class OhlcvCandle:
    source: CandleSource
    role: CandleRole
    category: str
    symbol: str
    interval: CandleInterval
    open_time: datetime
    close_time: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: Decimal
    turnover: Decimal

    def __post_init__(self) -> None:
        if self.role != CandleRole.STRUCTURE_DATA:
            raise ValueError("candle role must remain STRUCTURE_DATA")
        category = self.category.strip().lower()
        if category not in {"spot", "linear", "inverse"}:
            raise ValueError("unsupported candle category")
        symbol = self.symbol.strip().upper()
        if not symbol:
            raise ValueError("symbol is required")
        open_time = _aware(self.open_time, name="open_time")
        close_time = _aware(self.close_time, name="close_time")
        if close_time - open_time != self.interval.duration:
            raise ValueError("close_time must match interval duration")

        open_price = _decimal(self.open_price, name="open_price", positive=True)
        high_price = _decimal(self.high_price, name="high_price", positive=True)
        low_price = _decimal(self.low_price, name="low_price", positive=True)
        close_price = _decimal(self.close_price, name="close_price", positive=True)
        volume = _decimal(self.volume, name="volume")
        turnover = _decimal(self.turnover, name="turnover")

        if low_price > min(open_price, close_price):
            raise ValueError("low_price is inconsistent with open and close")
        if high_price < max(open_price, close_price):
            raise ValueError("high_price is inconsistent with open and close")
        if low_price > high_price:
            raise ValueError("candle range is inconsistent")

        object.__setattr__(self, "category", category)
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "open_time", open_time)
        object.__setattr__(self, "close_time", close_time)
        object.__setattr__(self, "open_price", open_price)
        object.__setattr__(self, "high_price", high_price)
        object.__setattr__(self, "low_price", low_price)
        object.__setattr__(self, "close_price", close_price)
        object.__setattr__(self, "volume", volume)
        object.__setattr__(self, "turnover", turnover)


@dataclass(frozen=True)
class CandleBatch:
    source: CandleSource
    role: CandleRole
    category: str
    symbol: str
    interval: CandleInterval
    fetched_at: datetime
    candles: tuple[OhlcvCandle, ...]

    def __post_init__(self) -> None:
        if self.role != CandleRole.STRUCTURE_DATA:
            raise ValueError("candle batch role must remain STRUCTURE_DATA")
        fetched_at = _aware(self.fetched_at, name="fetched_at")
        category = self.category.strip().lower()
        symbol = self.symbol.strip().upper()
        if category not in {"spot", "linear", "inverse"}:
            raise ValueError("unsupported candle category")
        if not symbol:
            raise ValueError("symbol is required")

        previous_open: datetime | None = None
        seen: set[datetime] = set()
        for candle in self.candles:
            if candle.source != self.source:
                raise ValueError("candle source mismatch")
            if candle.role != self.role:
                raise ValueError("candle role mismatch")
            if candle.category != category:
                raise ValueError("candle category mismatch")
            if candle.symbol != symbol:
                raise ValueError("candle symbol mismatch")
            if candle.interval != self.interval:
                raise ValueError("candle interval mismatch")
            if candle.close_time > fetched_at:
                raise ValueError("batch must contain only closed candles")
            if candle.open_time in seen:
                raise ValueError("duplicate candle open_time")
            if previous_open is not None and candle.open_time <= previous_open:
                raise ValueError("candles must be strictly chronological")
            seen.add(candle.open_time)
            previous_open = candle.open_time

        object.__setattr__(self, "category", category)
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "fetched_at", fetched_at)

    @property
    def latest(self) -> OhlcvCandle | None:
        return self.candles[-1] if self.candles else None
