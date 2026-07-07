from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class BenchmarkSource(StrEnum):
    MEXC = "MEXC"
    GATE = "GATE"
    BYBIT = "BYBIT"
    BINANCE = "BINANCE"


class BenchmarkRole(StrEnum):
    BENCHMARK_ONLY = "BENCHMARK_ONLY"


def _finite(value: Decimal, *, name: str) -> Decimal:
    if not isinstance(value, Decimal):
        try:
            value = Decimal(str(value))
        except Exception as error:
            raise ValueError(f"{name} must be decimal-compatible") from error
    if not value.is_finite():
        raise ValueError(f"{name} must be finite")
    return value


def _positive(value: Decimal, *, name: str) -> Decimal:
    value = _finite(value, name=name)
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _non_negative(value: Decimal, *, name: str) -> Decimal:
    value = _finite(value, name=name)
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


@dataclass(frozen=True)
class BenchmarkBookLevel:
    price: Decimal
    quantity: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "price", _positive(self.price, name="book price"))
        object.__setattr__(
            self,
            "quantity",
            _positive(self.quantity, name="book quantity"),
        )


@dataclass(frozen=True)
class BenchmarkSnapshot:
    source: BenchmarkSource
    role: BenchmarkRole
    symbol: str
    received_at: datetime
    latency_ms: int
    source_timestamp: datetime | None
    last_price: Decimal
    mark_price: Decimal | None
    index_price: Decimal | None
    funding_rate: Decimal | None
    open_interest: Decimal | None
    best_bid: Decimal
    best_ask: Decimal
    spread: Decimal
    spread_bps: Decimal
    bid_depth_quote: Decimal
    ask_depth_quote: Decimal

    def __post_init__(self) -> None:
        if self.role != BenchmarkRole.BENCHMARK_ONLY:
            raise ValueError("benchmark role must remain BENCHMARK_ONLY")
        symbol = self.symbol.strip()
        if not symbol:
            raise ValueError("symbol is required")
        if self.received_at.tzinfo is None or self.received_at.utcoffset() is None:
            raise ValueError("received_at must be timezone-aware")
        if self.source_timestamp is not None and (
            self.source_timestamp.tzinfo is None
            or self.source_timestamp.utcoffset() is None
        ):
            raise ValueError("source_timestamp must be timezone-aware")
        if isinstance(self.latency_ms, bool) or not isinstance(self.latency_ms, int):
            raise ValueError("latency_ms must be an integer")
        if self.latency_ms < 0:
            raise ValueError("latency_ms must be non-negative")

        last_price = _positive(self.last_price, name="last_price")
        mark_price = (
            _positive(self.mark_price, name="mark_price")
            if self.mark_price is not None
            else None
        )
        index_price = (
            _positive(self.index_price, name="index_price")
            if self.index_price is not None
            else None
        )
        funding_rate = (
            _finite(self.funding_rate, name="funding_rate")
            if self.funding_rate is not None
            else None
        )
        open_interest = (
            _non_negative(self.open_interest, name="open_interest")
            if self.open_interest is not None
            else None
        )
        best_bid = _positive(self.best_bid, name="best_bid")
        best_ask = _positive(self.best_ask, name="best_ask")
        if best_bid >= best_ask:
            raise ValueError("benchmark book must not be crossed or locked")
        spread = _positive(self.spread, name="spread")
        if spread != best_ask - best_bid:
            raise ValueError("spread does not match best bid and ask")
        spread_bps = _positive(self.spread_bps, name="spread_bps")
        bid_depth = _non_negative(self.bid_depth_quote, name="bid_depth_quote")
        ask_depth = _non_negative(self.ask_depth_quote, name="ask_depth_quote")

        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "last_price", last_price)
        object.__setattr__(self, "mark_price", mark_price)
        object.__setattr__(self, "index_price", index_price)
        object.__setattr__(self, "funding_rate", funding_rate)
        object.__setattr__(self, "open_interest", open_interest)
        object.__setattr__(self, "best_bid", best_bid)
        object.__setattr__(self, "best_ask", best_ask)
        object.__setattr__(self, "spread", spread)
        object.__setattr__(self, "spread_bps", spread_bps)
        object.__setattr__(self, "bid_depth_quote", bid_depth)
        object.__setattr__(self, "ask_depth_quote", ask_depth)
