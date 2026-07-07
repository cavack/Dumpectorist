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
        if self.received_at.tzinfo is None or self.received_at.utcoffset() is None:
            raise ValueError("received_at must be timezone-aware")
        if self.source_timestamp is not None and (
            self.source_timestamp.tzinfo is None
            or self.source_timestamp.utcoffset() is None
        ):
            raise ValueError("source_timestamp must be timezone-aware")
        if self.latency_ms < 0:
            raise ValueError("latency_ms must be non-negative")
