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
    require_object,
    require_text,
)
from app.adapters.parsers import ParserError


def _mexc_data(payload: Any, *, label: str) -> dict[str, Any]:
    root = require_object(payload, label=label)
    if root.get("success") is not True:
        raise ParserError(f"{label} reported failure")
    return require_object(root.get("data"), label=f"{label}.data")


class MexcUsdtPerpetualAdapter(BenchmarkAdapterBase):
    source_name = BenchmarkSource.MEXC.value
    name = "mexc-usdt-perpetual-benchmark"
    default_base_url = "https://contract.mexc.com"

    def __init__(
        self,
        *,
        symbol: str,
        depth: int = 20,
        base_url: str = default_base_url,
        client: JsonValueClient | None = None,
        clock=None,
    ) -> None:
        if depth < 1 or depth > 100:
            raise ValueError("MEXC depth must be between 1 and 100")
        self.depth = depth
        super().__init__(symbol=symbol, base_url=base_url, client=client, clock=clock)

    async def fetch_snapshot(self) -> BenchmarkSnapshot:
        started = perf_counter()
        detail_payload, ticker_payload, book_payload = await gather(
            self.client.get_json_value(
                self._url(f"/api/v1/contract/detail/{self.symbol}")
            ),
            self.client.get_json_value(
                self._url("/api/v1/contract/ticker"),
                params={"symbol": self.symbol},
            ),
            self.client.get_json_value(
                self._url(f"/api/v1/contract/depth/{self.symbol}"),
                params={"limit": self.depth},
            ),
        )

        detail = _mexc_data(detail_payload, label="detail")
        ticker = _mexc_data(ticker_payload, label="ticker")
        book = _mexc_data(book_payload, label="depth")

        detail_symbol = require_text(detail.get("symbol"), field="detail.symbol")
        ticker_symbol = require_text(ticker.get("symbol"), field="ticker.symbol")
        if detail_symbol != self.symbol or ticker_symbol != self.symbol:
            raise ParserError("MEXC symbol mismatch")
        if detail.get("quoteCoin") not in (None, "USDT"):
            raise ParserError("MEXC contract is not USDT quoted")
        if not self.symbol.endswith("_USDT"):
            raise ParserError("MEXC symbol must be a USDT perpetual contract")

        contract_size = parse_decimal(
            detail.get("contractSize"),
            field="detail.contractSize",
            positive=True,
        )
        bids = parse_sequence_book(
            book.get("bids"),
            side="bids",
            quantity_multiplier=contract_size,
        )
        asks = parse_sequence_book(
            book.get("asks"),
            side="asks",
            quantity_multiplier=contract_size,
        )
        best_bid, best_ask, spread, spread_bps, bid_depth, ask_depth = (
            calculate_book_metrics(bids, asks)
        )

        source_timestamp = ticker.get("timestamp") or book.get("timestamp")
        return BenchmarkSnapshot(
            source=BenchmarkSource.MEXC,
            role=BenchmarkRole.BENCHMARK_ONLY,
            symbol=self.symbol,
            received_at=self.received_at(),
            latency_ms=round((perf_counter() - started) * 1000),
            source_timestamp=parse_epoch_ms(
                source_timestamp,
                field="timestamp",
                optional=True,
            ),
            last_price=parse_decimal(
                ticker.get("lastPrice"),
                field="ticker.lastPrice",
                positive=True,
            ),
            mark_price=parse_decimal(
                ticker.get("fairPrice"),
                field="ticker.fairPrice",
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
                ticker.get("holdVol"),
                field="ticker.holdVol",
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
