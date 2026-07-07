from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import pytest

from app.adapters.coingecko import CoinGeckoDiscoveryAdapter, CoinGeckoFeed
from app.adapters.discovery_models import DiscoveryRole, DiscoverySource
from app.adapters.models import AdapterState
from app.adapters.source_cache import AsyncTtlCache, SlidingWindowBudget


NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)

MARKETS_PAYLOAD = [
    {
        "id": "bitcoin",
        "symbol": "btc",
        "name": "Bitcoin",
        "current_price": 60000,
        "market_cap": 1200000000000,
        "market_cap_rank": 1,
        "fully_diluted_valuation": 1260000000000,
        "total_volume": 35000000000,
        "price_change_percentage_24h": -1.25,
        "circulating_supply": 19800000,
        "total_supply": 21000000,
        "max_supply": 21000000,
        "ath": 73000,
        "atl": 67.81,
        "last_updated": "2026-07-07T12:00:00.000Z",
    }
]

CATEGORIES_PAYLOAD = [
    {
        "id": "layer-1",
        "name": "Layer 1 (L1)",
        "market_cap": 2100000000000,
        "market_cap_change_24h": -2.5,
        "content": "Layer-one networks.",
        "top_3_coins": ["bitcoin", "ethereum", "solana"],
        "volume_24h": 75000000000,
        "updated_at": "2026-07-07T12:00:00.000Z",
    }
]

UNIVERSE_PAYLOAD = [
    {"id": "bitcoin", "symbol": "btc", "name": "Bitcoin"},
    {"id": "ethereum", "symbol": "eth", "name": "Ethereum"},
]


class CoinGeckoFixtureClient:
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
async def test_markets_feed_maps_context_values():
    client = CoinGeckoFixtureClient(MARKETS_PAYLOAD)
    adapter = CoinGeckoDiscoveryAdapter(
        feed=CoinGeckoFeed.MARKETS,
        category="meme-token",
        page=2,
        per_page=50,
        client=client,
        clock=lambda: NOW,
    )

    batch = await adapter.fetch_batch()

    assert batch.source == DiscoverySource.COINGECKO
    assert batch.role == DiscoveryRole.DISCOVERY_ONLY
    assert batch.query == "markets:usd:meme-token:market_cap_desc:2:50"
    record = batch.records[0]
    assert record.external_id == "bitcoin"
    assert record.symbol == "BTC"
    assert record.name == "Bitcoin"
    assert record.category == "meme-token"
    assert record.price_usd == Decimal("60000")
    assert record.market_cap_usd == Decimal("1200000000000")
    assert record.volume_24h_usd == Decimal("35000000000")
    assert record.price_change_24h_pct == Decimal("-1.25")
    assert client.calls[0][1] == {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 50,
        "page": 2,
        "sparkline": "false",
        "price_change_percentage": "24h",
        "category": "meme-token",
    }


@pytest.mark.asyncio
async def test_categories_feed_maps_category_context():
    adapter = CoinGeckoDiscoveryAdapter(
        feed=CoinGeckoFeed.CATEGORIES,
        client=CoinGeckoFixtureClient(CATEGORIES_PAYLOAD),
        clock=lambda: NOW,
    )

    batch = await adapter.fetch_batch()

    record = batch.records[0]
    assert batch.query == "categories"
    assert record.external_id == "layer-1"
    assert record.category == "Layer 1 (L1)"
    assert record.market_cap_usd == Decimal("2100000000000")
    assert record.volume_24h_usd == Decimal("75000000000")
    assert record.price_change_24h_pct == Decimal("-2.5")


@pytest.mark.asyncio
async def test_universe_feed_has_no_execution_values():
    adapter = CoinGeckoDiscoveryAdapter(
        feed=CoinGeckoFeed.UNIVERSE,
        client=CoinGeckoFixtureClient(UNIVERSE_PAYLOAD),
        clock=lambda: NOW,
    )

    batch = await adapter.fetch_batch()

    assert len(batch.records) == 2
    assert batch.records[0].price_usd is None
    assert batch.records[0].liquidity_usd is None
    assert batch.records[0].symbol == "BTC"


@pytest.mark.asyncio
async def test_repeated_markets_request_uses_cache():
    client = CoinGeckoFixtureClient(MARKETS_PAYLOAD)
    cache: AsyncTtlCache[Any] = AsyncTtlCache(300)
    adapter = CoinGeckoDiscoveryAdapter(
        feed=CoinGeckoFeed.MARKETS,
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
async def test_malformed_market_degrades_generic_payload():
    adapter = CoinGeckoDiscoveryAdapter(
        feed=CoinGeckoFeed.MARKETS,
        client=CoinGeckoFixtureClient([{"id": "bitcoin"}]),
        clock=lambda: NOW,
    )

    payload = await adapter.load()

    assert payload.health.state == AdapterState.DEGRADED
    assert payload.data["role"] == "DISCOVERY_ONLY"
    assert payload.data["status"] == "DATA_DEGRADED"


def test_coingecko_configuration_is_validated():
    with pytest.raises(ValueError):
        CoinGeckoDiscoveryAdapter(feed=CoinGeckoFeed.MARKETS, page=0)
    with pytest.raises(ValueError):
        CoinGeckoDiscoveryAdapter(feed=CoinGeckoFeed.MARKETS, per_page=251)
    with pytest.raises(ValueError):
        CoinGeckoDiscoveryAdapter(
            feed=CoinGeckoFeed.MARKETS,
            base_url="http://example.test",
        )
