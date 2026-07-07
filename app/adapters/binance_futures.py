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


class BinanceUsdMAdapter(BenchmarkAdapterBase):
    source_name = BenchmarkSource.BINANCE.value
    name = "binance-usdm-benchmark"
    default_base_url = "https://fapi.binance.com"

    def __init__(
        self,
        *,
        symbol: str,
        depth: int = 20,
        base_url: str = default_base_url,
        client: JsonValueClient | None = None,
        clock=None,
    ) -> None:
        if depth not in {5, 10, 20, 50, 100, 500, 1000}:
            raise ValueError("unsupported Binance depth")
        self.depth = depth
        super().__init__(symbol=symbol, base_url=base_url, client=client, clock=clock)

    def _validate_contract(self, payload: Any) -> None:
        root = require_object(payload, label="exchangeInfo")
        symbols = require_list(root.get("symbols"), label="exchangeInfo.symbols")
        for raw in symbols:
            item = require_object(raw, label="exchangeInfo symbol")
            if item.get("symbol") != self.symbol:
                continue
            if item.get("contractType") != "PERPETUAL":
                raise ParserError("Binance contract is not perpetual")
            if item.get("quoteAsset") != "USDT" or item.get("marginAsset") != "USDT":
                raise ParserError("Binance contract is not USDT-margined")
            if item.get("status") != "TRADING":
                raise ParserError("Binance contract is not trading")
            return
        raise ParserError(f"symbol not found: {self.symbol}")

    async def fetch_snapshot(self) -> BenchmarkSnapshot:
        started = perf_counter()
        exchange_info, ticker, premium, open_interest, book = await gather(
            self.client.get_json_value(self._url("/fapi/v1/exchangeInfo")),
            self.client.get_json_value(
                self._url("/fapi/v2/ticker/price"),
                params={"symbol": self.symbol},
            ),
            self.client.get_json_value(
                self._url("/fapi/v1/premiumIndex"),
                params={"symbol": self.symbol},
            ),
            self.client.get_json_value(
                self._url("/fapi/v1/openInterest"),
                params={"symbol": self.symbol},
            ),
            self.client.get_json_value(
                self._url("/fapi/v1/depth"),
                params={"symbol": self.symbol, "limit": self.depth},
            ),
        )

        self._validate_contract(exchange_info)
        ticker_item = require_object(ticker, label="ticker")
        premium_item = require_object(premium, label="premiumIndex")
        interest_item = require_object(open_interest, label="openInterest")
        book_item = require_object(book, label="depth")

        for item, label in (
            (ticker_item, "ticker"),
            (premium_item, "premiumIndex"),
            (interest_item, "openInterest"),
        ):
            symbol = require_text(item.get("symbol"), field=f"{label}.symbol")
            if symbol != self.symbol:
                raise ParserError(f"{label} symbol mismatch")

        bids = parse_sequence_book(book_item.get("bids"), side="bids")
        asks = parse_sequence_book(book_item.get("asks"), side="asks")
        best_bid, best_ask, spread, spread_bps, bid_depth, ask_depth = (
            calculate_book_metrics(bids, asks)
        )

        return BenchmarkSnapshot(
            source=BenchmarkSource.BINANCE,
            role=BenchmarkRole.BENCHMARK_ONLY,
            symbol=self.symbol,
            received_at=self.received_at(),
            latency_ms=round((perf_counter() - started) * 1000),
            source_timestamp=parse_epoch_ms(
                premium_item.get("time"),
                field="premiumIndex.time",
                optional=True,
            ),
            last_price=parse_decimal(
                ticker_item.get("price"),
                field="ticker.price",
                positive=True,
            ),
            mark_price=parse_decimal(
                premium_item.get("markPrice"),
                field="premiumIndex.markPrice",
                positive=True,
            ),
            index_price=parse_decimal(
                premium_item.get("indexPrice"),
                field="premiumIndex.indexPrice",
                positive=True,
            ),
            funding_rate=parse_decimal(
                premium_item.get("lastFundingRate"),
                field="premiumIndex.lastFundingRate",
                optional=True,
            ),
            open_interest=parse_decimal(
                interest_item.get("openInterest"),
                field="openInterest.openInterest",
                non_negative=True,
            ),
            best_bid=best_bid,
            best_ask=best_ask,
            spread=spread,
            spread_bps=spread_bps,
            bid_depth_quote=bid_depth,
            ask_depth_quote=ask_depth,
        )
