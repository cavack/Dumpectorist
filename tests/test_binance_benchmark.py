from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import pytest

from app.adapters.benchmark_models import BenchmarkRole, BenchmarkSource
from app.adapters.binance_futures import BinanceUsdMAdapter
from app.adapters.models import AdapterState
from app.adapters.parsers import ParserError


NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)

EXCHANGE_INFO = {
    "symbols": [
        {
            "symbol": "BTCUSDT",
            "contractType": "PERPETUAL",
            "status": "TRADING",
            "quoteAsset": "USDT",
            "marginAsset": "USDT",
        }
    ]
}
TICKER = {"symbol": "BTCUSDT", "price": "60000.0", "time": 1783425600000}
PREMIUM = {
    "symbol": "BTCUSDT",
    "markPrice": "60001.0",
    "indexPrice": "59999.5",
    "lastFundingRate": "0.0001",
    "time": 1783425600000,
}
INTEREST = {"symbol": "BTCUSDT", "openInterest": "12345.67", "time": 1783425600000}
BOOK = {
    "lastUpdateId": 1,
    "E": 1783425600000,
    "T": 1783425600000,
    "bids": [["59999.0", "2.0"], ["59998.0", "3.0"]],
    "asks": [["60001.0", "1.5"], ["60002.0", "2.5"]],
}


class BinanceFixtureClient:
    def __init__(self, exchange_info: Any = EXCHANGE_INFO, book: Any = BOOK) -> None:
        self.exchange_info = exchange_info
        self.book = book
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    async def get_json_value(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        self.calls.append((url, params))
        if url.endswith("/exchangeInfo"):
            return self.exchange_info
        if url.endswith("/ticker/price"):
            return TICKER
        if url.endswith("/premiumIndex"):
            return PREMIUM
        if url.endswith("/openInterest"):
            return INTEREST
        if url.endswith("/depth"):
            return self.book
        raise AssertionError(f"unexpected URL: {url}")


@pytest.mark.asyncio
async def test_binance_adapter_builds_usdm_perpetual_snapshot():
    client = BinanceFixtureClient()
    adapter = BinanceUsdMAdapter(
        symbol="BTCUSDT",
        depth=20,
        client=client,
        clock=lambda: NOW,
    )

    snapshot = await adapter.fetch_snapshot()

    assert snapshot.source == BenchmarkSource.BINANCE
    assert snapshot.role == BenchmarkRole.BENCHMARK_ONLY
    assert snapshot.symbol == "BTCUSDT"
    assert snapshot.last_price == Decimal("60000.0")
    assert snapshot.mark_price == Decimal("60001.0")
    assert snapshot.index_price == Decimal("59999.5")
    assert snapshot.funding_rate == Decimal("0.0001")
    assert snapshot.open_interest == Decimal("12345.67")
    assert snapshot.best_bid == Decimal("59999.0")
    assert snapshot.best_ask == Decimal("60001.0")
    assert snapshot.spread == Decimal("2.0")
    assert snapshot.bid_depth_quote == Decimal("299992.0")
    assert snapshot.ask_depth_quote == Decimal("240006.5")
    assert snapshot.source_timestamp == NOW

    requested = {url.rsplit("/", 1)[-1]: params for url, params in client.calls}
    assert requested["exchangeInfo"] is None
    assert requested["price"] == {"symbol": "BTCUSDT"}
    assert requested["premiumIndex"] == {"symbol": "BTCUSDT"}
    assert requested["openInterest"] == {"symbol": "BTCUSDT"}
    assert requested["depth"] == {"symbol": "BTCUSDT", "limit": 20}


@pytest.mark.asyncio
async def test_binance_adapter_rejects_non_perpetual_contract():
    exchange_info = {
        "symbols": [
            {
                "symbol": "BTCUSDT",
                "contractType": "CURRENT_QUARTER",
                "status": "TRADING",
                "quoteAsset": "USDT",
                "marginAsset": "USDT",
            }
        ]
    }
    adapter = BinanceUsdMAdapter(
        symbol="BTCUSDT",
        client=BinanceFixtureClient(exchange_info=exchange_info),
        clock=lambda: NOW,
    )

    with pytest.raises(ParserError):
        await adapter.fetch_snapshot()


@pytest.mark.asyncio
async def test_binance_crossed_book_degrades_generic_payload():
    crossed = {"bids": [["60001", "1"]], "asks": [["60000", "1"]]}
    adapter = BinanceUsdMAdapter(
        symbol="BTCUSDT",
        client=BinanceFixtureClient(book=crossed),
        clock=lambda: NOW,
    )

    payload = await adapter.load()

    assert payload.health.state == AdapterState.DEGRADED
    assert payload.data["role"] == "BENCHMARK_ONLY"
    assert payload.data["status"] == "DATA_DEGRADED"


def test_binance_adapter_validates_depth_and_https():
    with pytest.raises(ValueError):
        BinanceUsdMAdapter(symbol="BTCUSDT", depth=7)
    with pytest.raises(ValueError):
        BinanceUsdMAdapter(symbol="BTCUSDT", base_url="http://example.test")
