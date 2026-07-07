from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import pytest

from app.adapters.benchmark_models import BenchmarkRole, BenchmarkSource
from app.adapters.bybit_futures import BybitLinearPerpetualAdapter
from app.adapters.gate_public import GateUsdtFuturesAdapter
from app.adapters.mexc_futures import MexcUsdtPerpetualAdapter
from app.adapters.parsers import ParserError


NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


class MexcFixtureClient:
    def __init__(self, *, ticker_symbol: str = "BTC_USDT") -> None:
        self.ticker_symbol = ticker_symbol

    async def get_json_value(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        if "/detail/" in url:
            return {
                "success": True,
                "data": {
                    "symbol": "BTC_USDT",
                    "quoteCoin": "USDT",
                    "contractSize": "0.001",
                },
            }
        if url.endswith("/ticker"):
            return {
                "success": True,
                "data": {
                    "symbol": self.ticker_symbol,
                    "lastPrice": "60000",
                    "fairPrice": "60001",
                    "indexPrice": "59999.5",
                    "fundingRate": "0.0001",
                    "holdVol": "12345",
                    "timestamp": 1783425600000,
                },
            }
        if "/depth/" in url:
            return {
                "success": True,
                "data": {
                    "bids": [["59999", "100"], ["59998", "200"]],
                    "asks": [["60001", "150"], ["60002", "250"]],
                    "timestamp": 1783425600000,
                },
            }
        raise AssertionError(f"unexpected URL: {url}")


class GateFixtureClient:
    async def get_json_value(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        if "/contracts/" in url:
            return {
                "name": "BTC_USDT",
                "quanto_multiplier": "0.0001",
                "in_delisting": False,
            }
        if url.endswith("/tickers"):
            return [
                {
                    "contract": "BTC_USDT",
                    "last": "60000",
                    "mark_price": "60001",
                    "index_price": "59999.5",
                    "funding_rate": "0.0001",
                    "total_size": "12345",
                }
            ]
        if url.endswith("/order_book"):
            return {
                "current": "1783425600.123",
                "bids": [{"p": "59999", "s": 100}, {"p": "59998", "s": 200}],
                "asks": [{"p": "60001", "s": -150}, {"p": "60002", "s": -250}],
            }
        raise AssertionError(f"unexpected URL: {url}")


class BybitFixtureClient:
    def __init__(self, *, contract_type: str = "LinearPerpetual") -> None:
        self.contract_type = contract_type

    async def get_json_value(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        if url.endswith("/instruments-info"):
            return {
                "retCode": 0,
                "result": {
                    "list": [
                        {
                            "symbol": "BTCUSDT",
                            "contractType": self.contract_type,
                            "status": "Trading",
                            "quoteCoin": "USDT",
                            "settleCoin": "USDT",
                        }
                    ]
                },
            }
        if url.endswith("/tickers"):
            return {
                "retCode": 0,
                "result": {
                    "list": [
                        {
                            "symbol": "BTCUSDT",
                            "lastPrice": "60000",
                            "markPrice": "60001",
                            "indexPrice": "59999.5",
                            "fundingRate": "0.0001",
                            "openInterest": "12345",
                        }
                    ]
                },
            }
        if url.endswith("/orderbook"):
            return {
                "retCode": 0,
                "result": {
                    "s": "BTCUSDT",
                    "b": [["59999", "2"], ["59998", "3"]],
                    "a": [["60001", "1.5"], ["60002", "2.5"]],
                    "ts": 1783425600000,
                },
            }
        raise AssertionError(f"unexpected URL: {url}")


@pytest.mark.asyncio
async def test_mexc_adapter_builds_benchmark_snapshot():
    adapter = MexcUsdtPerpetualAdapter(
        symbol="BTC_USDT",
        client=MexcFixtureClient(),
        clock=lambda: NOW,
    )

    snapshot = await adapter.fetch_snapshot()

    assert snapshot.source == BenchmarkSource.MEXC
    assert snapshot.role == BenchmarkRole.BENCHMARK_ONLY
    assert snapshot.last_price == Decimal("60000")
    assert snapshot.bid_depth_quote == Decimal("17999.5")
    assert snapshot.ask_depth_quote == Decimal("24000.65")
    assert snapshot.source_timestamp == NOW


@pytest.mark.asyncio
async def test_mexc_symbol_mismatch_is_rejected():
    adapter = MexcUsdtPerpetualAdapter(
        symbol="BTC_USDT",
        client=MexcFixtureClient(ticker_symbol="ETH_USDT"),
        clock=lambda: NOW,
    )

    with pytest.raises(ParserError):
        await adapter.fetch_snapshot()


@pytest.mark.asyncio
async def test_gate_adapter_builds_benchmark_snapshot():
    adapter = GateUsdtFuturesAdapter(
        symbol="BTC_USDT",
        client=GateFixtureClient(),
        clock=lambda: NOW,
    )

    snapshot = await adapter.fetch_snapshot()

    assert snapshot.source == BenchmarkSource.GATE
    assert snapshot.role == BenchmarkRole.BENCHMARK_ONLY
    assert snapshot.last_price == Decimal("60000")
    assert snapshot.bid_depth_quote == Decimal("1799.95")
    assert snapshot.ask_depth_quote == Decimal("2400.065")
    assert snapshot.source_timestamp == datetime(
        2026,
        7,
        7,
        12,
        0,
        0,
        123000,
        tzinfo=timezone.utc,
    )


@pytest.mark.asyncio
async def test_bybit_adapter_builds_benchmark_snapshot():
    adapter = BybitLinearPerpetualAdapter(
        symbol="BTCUSDT",
        depth=25,
        client=BybitFixtureClient(),
        clock=lambda: NOW,
    )

    snapshot = await adapter.fetch_snapshot()

    assert snapshot.source == BenchmarkSource.BYBIT
    assert snapshot.role == BenchmarkRole.BENCHMARK_ONLY
    assert snapshot.last_price == Decimal("60000")
    assert snapshot.bid_depth_quote == Decimal("299992")
    assert snapshot.ask_depth_quote == Decimal("240006.5")
    assert snapshot.source_timestamp == NOW


@pytest.mark.asyncio
async def test_bybit_non_perpetual_contract_is_rejected():
    adapter = BybitLinearPerpetualAdapter(
        symbol="BTCUSDT",
        client=BybitFixtureClient(contract_type="LinearFutures"),
        clock=lambda: NOW,
    )

    with pytest.raises(ParserError):
        await adapter.fetch_snapshot()


def test_other_adapters_validate_contract_symbol_shapes():
    with pytest.raises(ValueError):
        MexcUsdtPerpetualAdapter(symbol="BTC_USDT", depth=0)
    with pytest.raises(ValueError):
        GateUsdtFuturesAdapter(symbol="BTC_USDT", depth=101)
    with pytest.raises(ValueError):
        BybitLinearPerpetualAdapter(symbol="BTCUSDT", depth=10)
