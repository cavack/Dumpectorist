from asyncio import gather
from time import perf_counter
from typing import Any

from app.adapters.benchmark_base import BenchmarkAdapterBase, JsonValueClient
from app.adapters.benchmark_models import BenchmarkRole, BenchmarkSnapshot, BenchmarkSource
from app.adapters.benchmark_utils import (
    calculate_book_metrics,
    parse_decimal,
    parse_epoch_ms,
    parse_sequence_book,
    require_list,
    require_object,
    require_text,
)
from app.adapters.parsers import ParserError


def _bybit_result(payload: Any, *, label: str) -> dict[str, Any]:
    root = require_object(payload, label=label)
    if root.get("retCode") != 0:
        raise ParserError(f"{label} reported failure")
    return require_object(root.get("result"), label=f"{label}.result")


def _single_result_item(payload: Any, *, label: str) -> dict[str, Any]:
    result = _bybit_result(payload, label=label)
    items = require_list(result.get("list"), label=f"{label}.result.list")
    if len(items) != 1:
        raise ParserError(f"{label} must contain one symbol")
    return require_object(items[0], label=f"{label} item")


class BybitLinearPerpetualAdapter(BenchmarkAdapterBase):
    source_name = BenchmarkSource.BYBIT.value
    name = "bybit-linear-perpetual-benchmark"
    default_base_url = "https://api.bybit.com"

    def __init__(
        self,
        *,
        symbol: str,
        depth: int = 25,
        base_url: str = default_base_url,
        client: JsonValueClient | None = None,
        clock=None,
    ) -> None:
        if depth not in {1, 25, 50, 100, 200, 500}:
            raise ValueError("unsupported Bybit depth")
        self.depth = depth
        super().__init__(symbol=symbol, base_url=base_url, client=client, clock=clock)

    async def fetch_snapshot(self) -> BenchmarkSnapshot:
        started = perf_counter()
        instrument_payload, ticker_payload, book_payload = await gather(
            self.client.get_json_value(
                self._url("/v5/market/instruments-info"),
                params={"category": "linear", "symbol": self.symbol},
            ),
            self.client.get_json_value(
                self._url("/v5/market/tickers"),
                params={"category": "linear", "symbol": self.symbol},
            ),
            self.client.get_json_value(
                self._url("/v5/market/orderbook"),
                params={
                    "category": "linear",
                    "symbol": self.symbol,
                    "limit": self.depth,
                },
            ),
        )

        instrument = _single_result_item(instrument_payload, label="instruments")
        ticker = _single_result_item(ticker_payload, label="tickers")
        book = _bybit_result(book_payload, label="orderbook")

        for item, label in ((instrument, "instrument"), (ticker, "ticker")):
            symbol = require_text(item.get("symbol"), field=f"{label}.symbol")
            if symbol != self.symbol:
                raise ParserError(f"Bybit {label} symbol mismatch")
        if instrument.get("contractType") != "LinearPerpetual":
            raise ParserError("Bybit contract is not linear perpetual")
        if instrument.get("status") != "Trading":
            raise ParserError("Bybit contract is not trading")
        if instrument.get("quoteCoin") != "USDT" or instrument.get("settleCoin") != "USDT":
            raise ParserError("Bybit contract is not USDT-settled")

        book_symbol = require_text(book.get("s"), field="orderbook.s")
        if book_symbol != self.symbol:
            raise ParserError("Bybit order-book symbol mismatch")
        bids = parse_sequence_book(book.get("b"), side="bids")
        asks = parse_sequence_book(book.get("a"), side="asks")
        best_bid, best_ask, spread, spread_bps, bid_depth, ask_depth = (
            calculate_book_metrics(bids, asks)
        )

        return BenchmarkSnapshot(
            source=BenchmarkSource.BYBIT,
            role=BenchmarkRole.BENCHMARK_ONLY,
            symbol=self.symbol,
            received_at=self.received_at(),
            latency_ms=round((perf_counter() - started) * 1000),
            source_timestamp=parse_epoch_ms(
                book.get("ts"),
                field="orderbook.ts",
                optional=True,
            ),
            last_price=parse_decimal(
                ticker.get("lastPrice"),
                field="ticker.lastPrice",
                positive=True,
            ),
            mark_price=parse_decimal(
                ticker.get("markPrice"),
                field="ticker.markPrice",
                positive=True,
                optional=True,
            ),
            index_price=parse_decimal(
                ticker.get("indexPrice"),
                field="ticker.indexPrice",
                positive=True,
                optional=True,
            ),
            funding_rate=parse_decimal(
                ticker.get("fundingRate"),
                field="ticker.fundingRate",
                optional=True,
            ),
            open_interest=parse_decimal(
                ticker.get("openInterest"),
                field="ticker.openInterest",
                non_negative=True,
                optional=True,
            ),
            best_bid=best_bid,
            best_ask=best_ask,
            spread=spread,
            spread_bps=spread_bps,
            bid_depth_quote=bid_depth,
            ask_depth_quote=ask_depth,
        )
