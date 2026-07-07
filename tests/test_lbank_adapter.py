from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import pytest

from app.adapters.lbank import LBankPublicAdapter
from app.adapters.models import AdapterState
from app.adapters.parsers import ParserError


NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)

INSTRUMENTS = [
    {
        "baseCurrency": "BTC",
        "clearCurrency": "USDT",
        "defaultLeverage": 20,
        "exchangeID": "LBank",
        "maxOrderVolume": "1000",
        "minOrderCost": "5",
        "minOrderVolume": "1",
        "priceCurrency": "USDT",
        "priceLimitLowerValue": 0,
        "priceLimitUpperValue": 0,
        "priceTick": "0.1",
        "symbol": "BTCUSDT",
        "symbolName": "BTCUSDT",
        "volumeMultiple": "0.001",
        "volumeTick": "1",
    }
]

MARKET_DATA = [
    {
        "highestPrice": "62500",
        "lastPrice": "60000",
        "lowestPrice": "59000",
        "markedPrice": "60001",
        "openPrice": "60500",
        "prePositionFeeRate": "0.0001",
        "symbol": "BTCUSDT",
        "turnover": "15000000",
        "volume": "250000",
    }
]

ORDER_BOOK = {
    "asks": [
        {"orders": 2, "price": "60003", "volume": "20"},
        {"orders": 1, "price": "60002", "volume": "10"},
    ],
    "bids": [
        {"orders": 2, "price": "59998", "volume": "12"},
        {"orders": 1, "price": "59999", "volume": "8"},
    ],
    "symbol": "BTCUSDT",
}


class FixtureClient:
    def __init__(
        self,
        *,
        instruments: Any = INSTRUMENTS,
        market_data: Any = MARKET_DATA,
        order_book: Any = ORDER_BOOK,
    ) -> None:
        self.instruments = instruments
        self.market_data = market_data
        self.order_book = order_book
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    async def get_json_value(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        self.calls.append((url, params))
        if url.endswith("/getTime"):
            return {"success": True, "error_code": 0}
        if url.endswith("/instrument"):
            return self.instruments
        if url.endswith("/marketData"):
            return self.market_data
        if url.endswith("/marketOrder"):
            return self.order_book
        raise AssertionError(f"unexpected URL: {url}")


@pytest.mark.asyncio
async def test_adapter_builds_execution_snapshot():
    client = FixtureClient()
    adapter = LBankPublicAdapter(
        symbol="BTCUSDT",
        depth=20,
        client=client,
        clock=lambda: NOW,
    )

    snapshot = await adapter.fetch_snapshot()

    assert snapshot.symbol == "BTCUSDT"
    assert snapshot.product_group == "SwapU"
    assert snapshot.received_at == NOW
    assert snapshot.order_book.best_bid.price == Decimal("59999")
    assert snapshot.order_book.best_ask.price == Decimal("60002")
    assert snapshot.spread == Decimal("3")
    assert snapshot.spread_bps == pytest.approx(Decimal("0.5000041667"))
    assert snapshot.bid_depth_quote == Decimal("1199.976")
    assert snapshot.ask_depth_quote == Decimal("1800.08")
    assert snapshot.instrument.price_tick == Decimal("0.1")
    assert snapshot.quote.funding_rate == Decimal("0.0001")

    requested = {url.rsplit("/", 1)[-1]: params for url, params in client.calls}
    assert requested["instrument"] == {"productGroup": "SwapU"}
    assert requested["marketData"] == {"productGroup": "SwapU"}
    assert requested["marketOrder"] == {"symbol": "BTCUSDT", "depth": 20}


@pytest.mark.asyncio
async def test_adapter_load_returns_degraded_payload_for_missing_symbol():
    adapter = LBankPublicAdapter(
        symbol="MISSINGUSDT",
        client=FixtureClient(),
        clock=lambda: NOW,
    )

    payload = await adapter.load()

    assert payload.health.state == AdapterState.DEGRADED
    assert payload.health.message == "ParserError"
    assert payload.data["status"] == "DATA_DEGRADED"
    assert payload.data["symbol"] == "MISSINGUSDT"


@pytest.mark.asyncio
async def test_health_uses_public_time_endpoint():
    adapter = LBankPublicAdapter(symbol="BTCUSDT", client=FixtureClient())

    health = await adapter.health()

    assert health.state == AdapterState.OK
    assert health.latency_ms is not None


def test_adapter_requires_https_and_explicit_symbol():
    with pytest.raises(ValueError):
        LBankPublicAdapter(symbol=" ")
    with pytest.raises(ValueError):
        LBankPublicAdapter(symbol="BTCUSDT", base_url="http://example.test")


@pytest.mark.asyncio
async def test_crossed_order_book_is_rejected():
    crossed = {
        "asks": [{"orders": 1, "price": "60000", "volume": "1"}],
        "bids": [{"orders": 1, "price": "60001", "volume": "1"}],
        "symbol": "BTCUSDT",
    }
    adapter = LBankPublicAdapter(
        symbol="BTCUSDT",
        client=FixtureClient(order_book=crossed),
        clock=lambda: NOW,
    )

    with pytest.raises(ParserError):
        await adapter.fetch_snapshot()


@pytest.mark.asyncio
async def test_wrapper_data_lists_are_supported():
    adapter = LBankPublicAdapter(
        symbol="BTCUSDT",
        client=FixtureClient(
            instruments={"data": INSTRUMENTS},
            market_data={"data": MARKET_DATA},
            order_book={"data": ORDER_BOOK},
        ),
        clock=lambda: NOW,
    )

    snapshot = await adapter.fetch_snapshot()

    assert snapshot.symbol == "BTCUSDT"
