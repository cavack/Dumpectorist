from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import pytest

from app.adapters.dex_screener import DexScreenerAdapter, DexScreenerFeed
from app.adapters.discovery_models import DiscoveryRole, DiscoverySource
from app.adapters.models import AdapterState
from app.adapters.source_cache import AsyncTtlCache, SlidingWindowBudget


NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)

SEARCH_PAYLOAD = {
    "schemaVersion": "1.0.0",
    "pairs": [
        {
            "chainId": "solana",
            "dexId": "raydium",
            "url": "https://dexscreener.com/solana/pair-address",
            "pairAddress": "pair-address",
            "baseToken": {
                "address": "token-address",
                "name": "Bonk",
                "symbol": "BONK",
            },
            "quoteToken": {
                "address": "So11111111111111111111111111111111111111112",
                "name": "Wrapped SOL",
                "symbol": "SOL",
            },
            "priceUsd": "0.00001234",
            "volume": {"h24": 1250000.5},
            "priceChange": {"h24": -12.5},
            "liquidity": {"usd": 750000.25},
            "marketCap": 95000000,
            "pairCreatedAt": 1700000000000,
            "boosts": {"active": 10},
            "labels": ["CLMM"],
        }
    ],
}

BOOST_PAYLOAD = [
    {
        "url": "https://dexscreener.com/solana/4ekyor1hbhnrayyg2d57h36uuatrnyzr1nrp9scnpump",
        "chainId": "solana",
        "tokenAddress": "4eKYoR1hBHnRaYyg2d57H36uUatRNyZr1NRP9ScNpump",
        "description": "Captured boosted-token response shape.",
        "icon": "9DzCI49c9rvL_sPo",
        "links": [{"type": "twitter", "url": "https://x.com/example"}],
        "totalAmount": 10,
        "amount": 10,
    }
]


class DexFixtureClient:
    def __init__(self, payload: Any) -> None:
        self.payload = payload
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    async def get_json_value(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        self.calls.append((url, params))
        return self.payload


@pytest.mark.asyncio
async def test_search_pair_maps_to_discovery_record():
    client = DexFixtureClient(SEARCH_PAYLOAD)
    adapter = DexScreenerAdapter(
        feed=DexScreenerFeed.SEARCH,
        query="BONK",
        client=client,
        clock=lambda: NOW,
    )

    batch = await adapter.fetch_batch()

    assert batch.source == DiscoverySource.DEX_SCREENER
    assert batch.role == DiscoveryRole.DISCOVERY_ONLY
    assert batch.query == "search:BONK"
    assert batch.cache_hit is False
    assert len(batch.records) == 1
    record = batch.records[0]
    assert record.external_id == "pair-address"
    assert record.symbol == "BONK"
    assert record.chain_id == "solana"
    assert record.token_address == "token-address"
    assert record.price_usd == Decimal("0.00001234")
    assert record.liquidity_usd == Decimal("750000.25")
    assert record.volume_24h_usd == Decimal("1250000.5")
    assert record.market_cap_usd == Decimal("95000000")
    assert record.price_change_24h_pct == Decimal("-12.5")
    assert record.boost_active == 10
    assert record.pair_created_at is not None
    assert client.calls[0][1] == {"q": "BONK"}


@pytest.mark.asyncio
async def test_boost_feed_maps_captured_token_shape():
    adapter = DexScreenerAdapter(
        feed=DexScreenerFeed.BOOSTS,
        client=DexFixtureClient(BOOST_PAYLOAD),
        clock=lambda: NOW,
    )

    batch = await adapter.fetch_batch()

    record = batch.records[0]
    assert batch.query == "boosts:latest"
    assert record.external_id.startswith("solana:")
    assert record.boost_active == 10
    assert record.metadata["total_amount"] == 10


@pytest.mark.asyncio
async def test_repeated_search_uses_cache_without_second_request():
    client = DexFixtureClient(SEARCH_PAYLOAD)
    cache: AsyncTtlCache[Any] = AsyncTtlCache(60)
    adapter = DexScreenerAdapter(
        feed=DexScreenerFeed.SEARCH,
        query="BONK",
        client=client,
        cache=cache,
        budget=SlidingWindowBudget(1, 60),
        clock=lambda: NOW,
    )

    first = await adapter.fetch_batch()
    second = await adapter.fetch_batch()

    assert first.cache_hit is False
    assert second.cache_hit is True
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_malformed_pair_degrades_generic_payload():
    adapter = DexScreenerAdapter(
        feed=DexScreenerFeed.SEARCH,
        query="bad",
        client=DexFixtureClient({"pairs": [{"chainId": "solana"}]}),
        clock=lambda: NOW,
    )

    payload = await adapter.load()

    assert payload.health.state == AdapterState.DEGRADED
    assert payload.data["role"] == "DISCOVERY_ONLY"
    assert payload.data["status"] == "DATA_DEGRADED"
    assert payload.data["records"] == []


def test_feed_specific_arguments_are_required():
    with pytest.raises(ValueError):
        DexScreenerAdapter(feed=DexScreenerFeed.SEARCH)
    with pytest.raises(ValueError):
        DexScreenerAdapter(feed=DexScreenerFeed.TOKEN_PAIRS, chain_id="solana")
