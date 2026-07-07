from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Protocol

from app.adapters.benchmark_models import BenchmarkRole, BenchmarkSnapshot
from app.adapters.http_client import HttpClient
from app.adapters.models import AdapterHealth, AdapterPayload, AdapterState


class JsonValueClient(Protocol):
    async def get_json_value(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Return a decoded JSON value."""


class BenchmarkAdapterBase(ABC):
    source_name: str
    name: str

    def __init__(
        self,
        *,
        symbol: str,
        base_url: str,
        client: JsonValueClient | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        normalized_symbol = symbol.strip()
        normalized_url = base_url.rstrip("/")
        if not normalized_symbol:
            raise ValueError("symbol is required")
        if not normalized_url.startswith("https://"):
            raise ValueError("base_url must use HTTPS")

        self.symbol = normalized_symbol
        self.base_url = normalized_url
        self.client = client or HttpClient()
        self.clock = clock or utc_now

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def received_at(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("clock must return a timezone-aware datetime")
        return value

    @abstractmethod
    async def fetch_snapshot(self) -> BenchmarkSnapshot:
        """Fetch and parse one benchmark snapshot."""

    async def health(self) -> AdapterHealth:
        started = perf_counter()
        try:
            await self.fetch_snapshot()
        except Exception as error:
            return AdapterHealth(
                name=self.name,
                state=AdapterState.DOWN,
                latency_ms=round((perf_counter() - started) * 1000),
                message=type(error).__name__,
            )

        return AdapterHealth(
            name=self.name,
            state=AdapterState.OK,
            latency_ms=round((perf_counter() - started) * 1000),
        )

    async def load(self) -> AdapterPayload:
        try:
            snapshot = await self.fetch_snapshot()
        except Exception as error:
            state = AdapterState.DEGRADED if isinstance(error, ValueError) else AdapterState.DOWN
            return AdapterPayload(
                name=self.name,
                data={
                    "source": self.source_name,
                    "role": BenchmarkRole.BENCHMARK_ONLY.value,
                    "symbol": self.symbol,
                    "status": "DATA_DEGRADED",
                },
                health=AdapterHealth(
                    name=self.name,
                    state=state,
                    message=type(error).__name__,
                ),
            )

        return AdapterPayload(
            name=self.name,
            data={
                "source": snapshot.source.value,
                "role": snapshot.role.value,
                "symbol": snapshot.symbol,
                "received_at": snapshot.received_at.isoformat(),
                "source_timestamp": (
                    snapshot.source_timestamp.isoformat()
                    if snapshot.source_timestamp is not None
                    else None
                ),
                "latency_ms": snapshot.latency_ms,
                "last_price": str(snapshot.last_price),
                "mark_price": (
                    str(snapshot.mark_price) if snapshot.mark_price is not None else None
                ),
                "index_price": (
                    str(snapshot.index_price) if snapshot.index_price is not None else None
                ),
                "funding_rate": (
                    str(snapshot.funding_rate) if snapshot.funding_rate is not None else None
                ),
                "open_interest": (
                    str(snapshot.open_interest)
                    if snapshot.open_interest is not None
                    else None
                ),
                "best_bid": str(snapshot.best_bid),
                "best_ask": str(snapshot.best_ask),
                "spread": str(snapshot.spread),
                "spread_bps": str(snapshot.spread_bps),
                "bid_depth_quote": str(snapshot.bid_depth_quote),
                "ask_depth_quote": str(snapshot.ask_depth_quote),
                "status": "OK",
            },
            health=AdapterHealth(
                name=self.name,
                state=AdapterState.OK,
                latency_ms=snapshot.latency_ms,
            ),
        )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
