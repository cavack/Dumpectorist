from datetime import datetime, timezone

import pytest

from app.adapters.bybit_kline import BybitKlineAdapter
from app.adapters.models import AdapterState
from app.candles.models import CandleInterval

NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


class StaticClient:
    def __init__(self, payload):
        self.payload = payload

    async def get_json_value(self, url, params=None):
        return self.payload


class ErrorClient:
    async def get_json_value(self, url, params=None):
        raise RuntimeError("unavailable")


def ms(value: datetime) -> int:
    return round(value.timestamp() * 1000)


def row(value: datetime):
    return [ms(value), "100", "102", "99", "101", "10", "1005"]


def response(rows, *, symbol="BTCUSDT", category="linear", code=0):
    return {
        "retCode": code,
        "result": {"symbol": symbol, "category": category, "list": rows},
    }


@pytest.mark.asyncio
async def test_adapter_keeps_only_closed_rows_in_chronological_order():
    rows = [
        row(datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)),
        row(datetime(2026, 7, 7, 8, 0, tzinfo=timezone.utc)),
        row(datetime(2026, 7, 7, 4, 0, tzinfo=timezone.utc)),
    ]
    adapter = BybitKlineAdapter(
        symbol="BTCUSDT",
        interval=CandleInterval.H4,
        limit=3,
        client=StaticClient(response(rows)),
        clock=lambda: NOW,
    )

    batch = await adapter.fetch_batch()

    assert [item.open_time.hour for item in batch.candles] == [4, 8]
    assert all(item.close_time <= NOW for item in batch.candles)


@pytest.mark.asyncio
async def test_adapter_reports_ok_for_fresh_closed_rows():
    adapter = BybitKlineAdapter(
        symbol="BTCUSDT",
        interval=CandleInterval.H4,
        client=StaticClient(
            response([row(datetime(2026, 7, 7, 8, 0, tzinfo=timezone.utc))])
        ),
        clock=lambda: NOW,
    )

    payload = await adapter.load()

    assert payload.health.state == AdapterState.OK
    assert payload.data["status"] == "OK"
    assert len(payload.data["candles"]) == 1


@pytest.mark.asyncio
async def test_adapter_reports_empty_without_creating_rows():
    adapter = BybitKlineAdapter(
        symbol="BTCUSDT",
        interval=CandleInterval.H4,
        client=StaticClient(
            response([row(datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc))])
        ),
        clock=lambda: NOW,
    )

    payload = await adapter.load()

    assert payload.health.state == AdapterState.DEGRADED
    assert payload.data["status"] == "EMPTY"
    assert payload.data["candles"] == []


@pytest.mark.asyncio
async def test_parser_and_transport_failures_are_controlled():
    parser_adapter = BybitKlineAdapter(
        symbol="BTCUSDT",
        interval=CandleInterval.H4,
        client=StaticClient(response([], code=1)),
        clock=lambda: NOW,
    )
    transport_adapter = BybitKlineAdapter(
        symbol="BTCUSDT",
        interval=CandleInterval.H4,
        client=ErrorClient(),
        clock=lambda: NOW,
    )

    parser_payload = await parser_adapter.load()
    transport_payload = await transport_adapter.load()

    assert parser_payload.health.state == AdapterState.DEGRADED
    assert transport_payload.health.state == AdapterState.DOWN
    assert parser_payload.data["candles"] == []
    assert transport_payload.data["candles"] == []


def test_constructor_rejects_invalid_values():
    with pytest.raises(ValueError):
        BybitKlineAdapter(symbol=" ", interval=CandleInterval.H4)
    with pytest.raises(ValueError):
        BybitKlineAdapter(symbol="BTCUSDT", interval=CandleInterval.H4, limit=0)
    with pytest.raises(ValueError):
        BybitKlineAdapter(
            symbol="BTCUSDT",
            interval=CandleInterval.H4,
            base_url="http://example.test",
        )
