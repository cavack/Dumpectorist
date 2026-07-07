from enum import StrEnum
from typing import Any

from app.adapters.benchmark_utils import parse_decimal, require_list, require_object, require_text
from app.adapters.discovery_base import DiscoveryAdapterBase, JsonValueClient
from app.adapters.discovery_models import (
    DiscoveryBatch,
    DiscoveryRecord,
    DiscoveryRole,
    DiscoverySource,
)
from app.adapters.source_cache import AsyncTtlCache, SlidingWindowBudget


class CoinGeckoFeed(StrEnum):
    MARKETS = "MARKETS"
    CATEGORIES = "CATEGORIES"
    UNIVERSE = "UNIVERSE"


class CoinGeckoDiscoveryAdapter(DiscoveryAdapterBase):
    source_name = DiscoverySource.COINGECKO.value
    name = "coingecko-discovery"
    default_base_url = "https://api.coingecko.com/api/v3"

    def __init__(
        self,
        *,
        feed: CoinGeckoFeed,
        category: str | None = None,
        page: int = 1,
        per_page: int = 100,
        order: str = "market_cap_desc",
        vs_currency: str = "usd",
        base_url: str = default_base_url,
        client: JsonValueClient | None = None,
        cache: AsyncTtlCache[Any] | None = None,
        budget: SlidingWindowBudget | None = None,
        clock=None,
        ttl_seconds: float = 300.0,
        max_requests_per_minute: int = 30,
    ) -> None:
        if page < 1:
            raise ValueError("page must be positive")
        if per_page < 1 or per_page > 250:
            raise ValueError("per_page must be between 1 and 250")
        normalized_currency = vs_currency.strip().lower()
        if not normalized_currency:
            raise ValueError("vs_currency is required")

        self.feed = feed
        self.category = category.strip() if category is not None else None
        self.page = page
        self.per_page = per_page
        self.order = order.strip()
        self.vs_currency = normalized_currency
        if not self.order:
            raise ValueError("order is required")

        super().__init__(
            base_url=base_url,
            ttl_seconds=ttl_seconds,
            max_requests_per_minute=max_requests_per_minute,
            client=client,
            cache=cache,
            budget=budget,
            clock=clock,
        )

    def _request(self) -> tuple[str, str, dict[str, Any] | None]:
        if self.feed == CoinGeckoFeed.CATEGORIES:
            return "categories", self._url("/coins/categories"), None
        if self.feed == CoinGeckoFeed.UNIVERSE:
            return (
                "universe",
                self._url("/coins/list"),
                {"include_platform": "false"},
            )

        params: dict[str, Any] = {
            "vs_currency": self.vs_currency,
            "order": self.order,
            "per_page": self.per_page,
            "page": self.page,
            "sparkline": "false",
            "price_change_percentage": "24h",
        }
        if self.category:
            params["category"] = self.category
        key = (
            f"markets:{self.vs_currency}:{self.category or 'all'}:"
            f"{self.order}:{self.page}:{self.per_page}"
        )
        return key, self._url("/coins/markets"), params

    def _market_record(self, item: dict[str, Any]) -> DiscoveryRecord:
        external_id = require_text(item.get("id"), field="id")
        symbol = require_text(item.get("symbol"), field="symbol")
        name = require_text(item.get("name"), field="name")
        return DiscoveryRecord(
            source=DiscoverySource.COINGECKO,
            role=DiscoveryRole.DISCOVERY_ONLY,
            external_id=external_id,
            symbol=symbol.upper(),
            name=name,
            category=self.category,
            price_usd=parse_decimal(
                item.get("current_price"),
                field="current_price",
                non_negative=True,
                optional=True,
            ),
            volume_24h_usd=parse_decimal(
                item.get("total_volume"),
                field="total_volume",
                non_negative=True,
                optional=True,
            ),
            market_cap_usd=parse_decimal(
                item.get("market_cap"),
                field="market_cap",
                non_negative=True,
                optional=True,
            ),
            price_change_24h_pct=parse_decimal(
                item.get("price_change_percentage_24h"),
                field="price_change_percentage_24h",
                optional=True,
            ),
            metadata={
                "market_cap_rank": item.get("market_cap_rank"),
                "fully_diluted_valuation": item.get("fully_diluted_valuation"),
                "circulating_supply": item.get("circulating_supply"),
                "total_supply": item.get("total_supply"),
                "max_supply": item.get("max_supply"),
                "ath": item.get("ath"),
                "atl": item.get("atl"),
                "last_updated": item.get("last_updated"),
            },
        )

    @staticmethod
    def _category_record(item: dict[str, Any]) -> DiscoveryRecord:
        external_id = require_text(item.get("id"), field="id")
        name = require_text(item.get("name"), field="name")
        return DiscoveryRecord(
            source=DiscoverySource.COINGECKO,
            role=DiscoveryRole.DISCOVERY_ONLY,
            external_id=external_id,
            name=name,
            category=name,
            market_cap_usd=parse_decimal(
                item.get("market_cap"),
                field="market_cap",
                non_negative=True,
                optional=True,
            ),
            volume_24h_usd=parse_decimal(
                item.get("volume_24h"),
                field="volume_24h",
                non_negative=True,
                optional=True,
            ),
            price_change_24h_pct=parse_decimal(
                item.get("market_cap_change_24h"),
                field="market_cap_change_24h",
                optional=True,
            ),
            metadata={
                "content": item.get("content"),
                "top_3_coins": item.get("top_3_coins", []),
                "updated_at": item.get("updated_at"),
            },
        )

    @staticmethod
    def _universe_record(item: dict[str, Any]) -> DiscoveryRecord:
        external_id = require_text(item.get("id"), field="id")
        symbol = require_text(item.get("symbol"), field="symbol")
        name = require_text(item.get("name"), field="name")
        return DiscoveryRecord(
            source=DiscoverySource.COINGECKO,
            role=DiscoveryRole.DISCOVERY_ONLY,
            external_id=external_id,
            symbol=symbol.upper(),
            name=name,
        )

    async def fetch_batch(self) -> DiscoveryBatch:
        cache_key, url, params = self._request()
        payload, cache_hit = await self.request_json(
            cache_key=cache_key,
            url=url,
            params=params,
        )
        raw_records = require_list(payload, label=self.feed.value.lower())
        records: list[DiscoveryRecord] = []
        for raw in raw_records:
            item = require_object(raw, label="record")
            if self.feed == CoinGeckoFeed.MARKETS:
                records.append(self._market_record(item))
            elif self.feed == CoinGeckoFeed.CATEGORIES:
                records.append(self._category_record(item))
            else:
                records.append(self._universe_record(item))

        return DiscoveryBatch(
            source=DiscoverySource.COINGECKO,
            role=DiscoveryRole.DISCOVERY_ONLY,
            query=cache_key,
            fetched_at=self.fetched_at(),
            records=tuple(records),
            cache_hit=cache_hit,
        )
