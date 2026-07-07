from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Protocol

from app.adapters.discovery_models import DiscoveryBatch, DiscoveryRole
from app.adapters.http_client import HttpClient
from app.adapters.models import AdapterHealth, AdapterPayload, AdapterState
from app.adapters.source_cache import (
    AsyncTtlCache,
    RequestBudgetExceeded,
    SlidingWindowBudget,
)


class JsonValueClient(Protocol):
    async def get_json_value(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Return a decoded JSON value."""


class DiscoveryAdapterBase(ABC):
    source_name: str
    name: str

    def __init__(
        self,
        *,
        base_url: str,
        ttl_seconds: float,
        max_requests_per_minute: int,
        client: JsonValueClient | None = None,
        cache: AsyncTtlCache[Any] | None = None,
        budget: SlidingWindowBudget | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        normalized_url = base_url.rstrip("/")
        if not normalized_url.startswith("https://"):
            raise ValueError("base_url must use HTTPS")
        self.base_url = normalized_url
        self.client = client or HttpClient()
        self.cache = cache or AsyncTtlCache(ttl_seconds)
        self.budget = budget or SlidingWindowBudget(max_requests_per_minute, 60.0)
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def fetched_at(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("clock must return a timezone-aware datetime")
        return value

    async def request_json(
        self,
        *,
        cache_key: str,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> tuple[Any, bool]:
        cached = await self.cache.get(cache_key)
        if cached is not None:
            return cached, True
        await self.budget.acquire()
        payload = await self.client.get_json_value(url, params=params)
        await self.cache.set(cache_key, payload)
        return payload, False

    @abstractmethod
    async def fetch_batch(self) -> DiscoveryBatch:
        """Fetch one discovery batch."""

    async def health(self) -> AdapterHealth:
        started = perf_counter()
        try:
            await self.fetch_batch()
        except Exception as error:
            state = (
                AdapterState.DEGRADED
                if isinstance(error, (ValueError, RequestBudgetExceeded))
                else AdapterState.DOWN
            )
            return AdapterHealth(
                name=self.name,
                state=state,
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
            batch = await self.fetch_batch()
        except Exception as error:
            state = (
                AdapterState.DEGRADED
                if isinstance(error, (ValueError, RequestBudgetExceeded))
                else AdapterState.DOWN
            )
            return AdapterPayload(
                name=self.name,
                data={
                    "source": self.source_name,
                    "role": DiscoveryRole.DISCOVERY_ONLY.value,
                    "status": "DATA_DEGRADED",
                    "records": [],
                },
                health=AdapterHealth(
                    name=self.name,
                    state=state,
                    message=type(error).__name__,
                ),
            )

        records: list[dict[str, Any]] = []
        for record in batch.records:
            item = asdict(record)
            item["source"] = record.source.value
            item["role"] = record.role.value
            for field in (
                "price_usd",
                "liquidity_usd",
                "volume_24h_usd",
                "market_cap_usd",
                "price_change_24h_pct",
            ):
                value = item[field]
                item[field] = str(value) if value is not None else None
            if record.pair_created_at is not None:
                item["pair_created_at"] = record.pair_created_at.isoformat()
            records.append(item)

        return AdapterPayload(
            name=self.name,
            data={
                "source": batch.source.value,
                "role": batch.role.value,
                "query": batch.query,
                "fetched_at": batch.fetched_at.isoformat(),
                "cache_hit": batch.cache_hit,
                "status": "OK",
                "records": records,
            },
            health=AdapterHealth(name=self.name, state=AdapterState.OK),
        )
