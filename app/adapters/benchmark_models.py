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


@dataclass(frozen=True)
class BenchmarkBookLevel:
    price: Decimal
    quantity: Decimal

    def __post_init__(self) -> None:
        if self.price <= 0:
            raise ValueError("book price must be positive")
        if self.quantity <= 0:
            raise ValueError("book quantity must be positive")


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
        if not self.symbol.strip():
            raise ValueError("symbol is required")
        if self.received_at.tzinfo is None or self.received_at.utcoffset() is None:
            raise ValueError("received_at must be timezone-aware")
        if self.source_timestamp is not None and (
            self.source_timestamp.tzinfo is None
            or self.source_timestamp.utcoffset() is None
        ):
            raise ValueError("source_timestamp must be timezone-aware")
        if self.latency_ms < 0:
            raise ValueError("latency_ms must be non-negative")
        if self.last_price <= 0:
            raise ValueError("last_price must be positive")
        if self.mark_price is not None and self.mark_price <= 0:
            raise ValueError("mark_price must be positive")
        if self.index_price is not None and self.index_price <= 0:
            raise ValueError("index_price must be positive")
        if self.open_interest is not None and self.open_interest < 0:
            raise ValueError("open_interest must be non-negative")
        if self.best_bid <= 0 or self.best_ask <= 0:
            raise ValueError("best bid and ask must be positive")
        if self.best_bid >= self.best_ask:
            raise ValueError("benchmark book must not be crossed or locked")
        if self.spread != self.best_ask - self.best_bid:
            raise ValueError("spread does not match best bid and ask")
        if self.spread <= 0 or self.spread_bps <= 0:
            raise ValueError("spread values must be positive")
        if self.bid_depth_quote < 0 or self.ask_depth_quote < 0:
            raise ValueError("depth values must be non-negative")
