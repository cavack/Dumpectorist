from enum import StrEnum
from typing import Any

from app.adapters.benchmark_utils import (
    parse_decimal,
    parse_epoch_ms,
    require_list,
    require_object,
    require_text,
)
from app.adapters.discovery_base import DiscoveryAdapterBase, JsonValueClient
from app.adapters.discovery_models import (
    DiscoveryBatch,
    DiscoveryRecord,
    DiscoveryRole,
    DiscoverySource,
)
from app.adapters.parsers import ParserError
from app.adapters.source_cache import AsyncTtlCache, SlidingWindowBudget


class DexScreenerFeed(StrEnum):
    BOOSTS = "BOOSTS"
    PROFILES = "PROFILES"
    SEARCH = "SEARCH"
    TOKEN_PAIRS = "TOKEN_PAIRS"


class DexScreenerAdapter(DiscoveryAdapterBase):
    source_name = DiscoverySource.DEX_SCREENER.value
    name = "dex-screener-discovery"
    default_base_url = "https://api.dexscreener.com"

    def __init__(
        self,
        *,
        feed: DexScreenerFeed,
        query: str | None = None,
        chain_id: str | None = None,
        token_address: str | None = None,
        base_url: str = default_base_url,
        client: JsonValueClient | None = None,
        cache: AsyncTtlCache[Any] | None = None,
        budget: SlidingWindowBudget | None = None,
        clock=None,
        ttl_seconds: float = 60.0,
    ) -> None:
        self.feed = feed
        self.query = query.strip() if query is not None else None
        self.chain_id = chain_id.strip() if chain_id is not None else None
        self.token_address = token_address.strip() if token_address is not None else None

        if feed == DexScreenerFeed.SEARCH and not self.query:
            raise ValueError("query is required for SEARCH")
        if feed == DexScreenerFeed.TOKEN_PAIRS and (
            not self.chain_id or not self.token_address
        ):
            raise ValueError("chain_id and token_address are required for TOKEN_PAIRS")

        max_requests = 60 if feed in {
            DexScreenerFeed.BOOSTS,
            DexScreenerFeed.PROFILES,
        } else 300
        super().__init__(
            base_url=base_url,
            ttl_seconds=ttl_seconds,
            max_requests_per_minute=max_requests,
            client=client,
            cache=cache,
            budget=budget,
            clock=clock,
        )

    def _request(self) -> tuple[str, str, dict[str, Any] | None]:
        if self.feed == DexScreenerFeed.BOOSTS:
            return "boosts:latest", self._url("/token-boosts/latest/v1"), None
        if self.feed == DexScreenerFeed.PROFILES:
            return "profiles:latest", self._url("/token-profiles/latest/v1"), None
        if self.feed == DexScreenerFeed.SEARCH:
            return (
                f"search:{self.query}",
                self._url("/latest/dex/search"),
                {"q": self.query},
            )
        return (
            f"pairs:{self.chain_id}:{self.token_address}",
            self._url(f"/token-pairs/v1/{self.chain_id}/{self.token_address}"),
            None,
        )

    @staticmethod
    def _records_payload(payload: Any, *, feed: DexScreenerFeed) -> list[Any]:
        if feed == DexScreenerFeed.SEARCH:
            root = require_object(payload, label="search")
            return require_list(root.get("pairs"), label="search.pairs")
        if isinstance(payload, dict):
            return [payload]
        return require_list(payload, label=feed.value.lower())

    @staticmethod
    def _token_record(item: dict[str, Any], *, feed: DexScreenerFeed) -> DiscoveryRecord:
        chain_id = require_text(item.get("chainId"), field="chainId")
        token_address = require_text(item.get("tokenAddress"), field="tokenAddress")
        amount = item.get("amount")
        total_amount = item.get("totalAmount")
        links = item.get("links") if isinstance(item.get("links"), list) else []
        return DiscoveryRecord(
            source=DiscoverySource.DEX_SCREENER,
            role=DiscoveryRole.DISCOVERY_ONLY,
            external_id=f"{chain_id}:{token_address}",
            chain_id=chain_id,
            token_address=token_address,
            boost_active=(
                int(amount)
                if feed == DexScreenerFeed.BOOSTS and isinstance(amount, int)
                else None
            ),
            url=item.get("url") if isinstance(item.get("url"), str) else None,
            metadata={
                "feed": feed.value,
                "description": item.get("description"),
                "icon": item.get("icon"),
                "header": item.get("header"),
                "links": links,
                "amount": amount,
                "total_amount": total_amount,
            },
        )

    @staticmethod
    def _pair_record(item: dict[str, Any]) -> DiscoveryRecord:
        pair_address = require_text(item.get("pairAddress"), field="pairAddress")
        chain_id = require_text(item.get("chainId"), field="chainId")
        base_token = require_object(item.get("baseToken"), label="baseToken")
        token_address = require_text(base_token.get("address"), field="baseToken.address")
        symbol = require_text(base_token.get("symbol"), field="baseToken.symbol")
        name = base_token.get("name") if isinstance(base_token.get("name"), str) else None

        liquidity = item.get("liquidity") if isinstance(item.get("liquidity"), dict) else {}
        volume = item.get("volume") if isinstance(item.get("volume"), dict) else {}
        change = item.get("priceChange") if isinstance(item.get("priceChange"), dict) else {}
        boosts = item.get("boosts") if isinstance(item.get("boosts"), dict) else {}

        boost_active = boosts.get("active")
        if boost_active is not None and (
            isinstance(boost_active, bool) or not isinstance(boost_active, int)
        ):
            raise ParserError("boosts.active must be an integer")

        return DiscoveryRecord(
            source=DiscoverySource.DEX_SCREENER,
            role=DiscoveryRole.DISCOVERY_ONLY,
            external_id=pair_address,
            symbol=symbol,
            name=name,
            chain_id=chain_id,
            token_address=token_address,
            price_usd=parse_decimal(
                item.get("priceUsd"),
                field="priceUsd",
                non_negative=True,
                optional=True,
            ),
            liquidity_usd=parse_decimal(
                liquidity.get("usd"),
                field="liquidity.usd",
                non_negative=True,
                optional=True,
            ),
            volume_24h_usd=parse_decimal(
                volume.get("h24"),
                field="volume.h24",
                non_negative=True,
                optional=True,
            ),
            market_cap_usd=parse_decimal(
                item.get("marketCap"),
                field="marketCap",
                non_negative=True,
                optional=True,
            ),
            price_change_24h_pct=parse_decimal(
                change.get("h24"),
                field="priceChange.h24",
                optional=True,
            ),
            boost_active=boost_active,
            pair_created_at=parse_epoch_ms(
                item.get("pairCreatedAt"),
                field="pairCreatedAt",
                optional=True,
            ),
            url=item.get("url") if isinstance(item.get("url"), str) else None,
            metadata={
                "dex_id": item.get("dexId"),
                "quote_token": item.get("quoteToken"),
                "labels": item.get("labels", []),
            },
        )

    async def fetch_batch(self) -> DiscoveryBatch:
        cache_key, url, params = self._request()
        payload, cache_hit = await self.request_json(
            cache_key=cache_key,
            url=url,
            params=params,
        )
        raw_records = self._records_payload(payload, feed=self.feed)
        records: list[DiscoveryRecord] = []
        for raw in raw_records:
            item = require_object(raw, label="record")
            if self.feed in {DexScreenerFeed.BOOSTS, DexScreenerFeed.PROFILES}:
                records.append(self._token_record(item, feed=self.feed))
            else:
                records.append(self._pair_record(item))

        return DiscoveryBatch(
            source=DiscoverySource.DEX_SCREENER,
            role=DiscoveryRole.DISCOVERY_ONLY,
            query=cache_key,
            fetched_at=self.fetched_at(),
            records=tuple(records),
            cache_hit=cache_hit,
        )
