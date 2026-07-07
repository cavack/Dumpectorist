from asyncio import gather
from time import perf_counter

from app.adapters.benchmark_base import BenchmarkAdapterBase, JsonValueClient
from app.adapters.benchmark_models import BenchmarkRole, BenchmarkSnapshot, BenchmarkSource
from app.adapters.benchmark_utils import (
    calculate_book_metrics,
    parse_decimal,
    parse_epoch_seconds,
    parse_object_book,
    require_list,
    require_object,
    require_text,
)
from app.adapters.parsers import ParserError


class GateUsdtFuturesAdapter(BenchmarkAdapterBase):
    source_name = BenchmarkSource.GATE.value
    name = "gate-usdt-futures-benchmark"
    default_base_url = "https://api.gateio.ws"

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
            raise ValueError("Gate depth must be between 1 and 100")
        self.depth = depth
        super().__init__(symbol=symbol, base_url=base_url, client=client, clock=clock)

    async def fetch_snapshot(self) -> BenchmarkSnapshot:
        started = perf_counter()
        contract_payload, ticker_payload, book_payload = await gather(
            self.client.get_json_value(
                self._url(f"/api/v4/futures/usdt/contracts/{self.symbol}")
            ),
            self.client.get_json_value(
                self._url("/api/v4/futures/usdt/tickers"),
                params={"contract": self.symbol},
            ),
            self.client.get_json_value(
                self._url("/api/v4/futures/usdt/order_book"),
                params={
                    "contract": self.symbol,
                    "limit": self.depth,
                    "with_id": True,
                },
            ),
        )

        contract = require_object(contract_payload, label="contract")
        contract_name = require_text(contract.get("name"), field="contract.name")
        if contract_name != self.symbol:
            raise ParserError("Gate contract symbol mismatch")
        if not self.symbol.endswith("_USDT"):
            raise ParserError("Gate symbol must be a USDT futures contract")
        if contract.get("in_delisting") is True:
            raise ParserError("Gate contract is delisting")

        multiplier = parse_decimal(
            contract.get("quanto_multiplier"),
            field="contract.quanto_multiplier",
            positive=True,
        )
        tickers = require_list(ticker_payload, label="tickers")
        if len(tickers) != 1:
            raise ParserError("Gate ticker response must contain one contract")
        ticker = require_object(tickers[0], label="ticker")
        ticker_symbol = require_text(ticker.get("contract"), field="ticker.contract")
        if ticker_symbol != self.symbol:
            raise ParserError("Gate ticker symbol mismatch")

        book = require_object(book_payload, label="order_book")
        bids = parse_object_book(
            book.get("bids"),
            side="bids",
            price_field="p",
            quantity_field="s",
            quantity_multiplier=multiplier,
            absolute_quantity=True,
        )
        asks = parse_object_book(
            book.get("asks"),
            side="asks",
            price_field="p",
            quantity_field="s",
            quantity_multiplier=multiplier,
            absolute_quantity=True,
        )
        best_bid, best_ask, spread, spread_bps, bid_depth, ask_depth = (
            calculate_book_metrics(bids, asks)
        )

        return BenchmarkSnapshot(
            source=BenchmarkSource.GATE,
            role=BenchmarkRole.BENCHMARK_ONLY,
            symbol=self.symbol,
            received_at=self.received_at(),
            latency_ms=round((perf_counter() - started) * 1000),
            source_timestamp=parse_epoch_seconds(
                book.get("current"),
                field="order_book.current",
                optional=True,
            ),
            last_price=parse_decimal(
                ticker.get("last"),
                field="ticker.last",
                positive=True,
            ),
            mark_price=parse_decimal(
                ticker.get("mark_price"),
                field="ticker.mark_price",
                positive=True,
                optional=True,
            ),
            index_price=parse_decimal(
                ticker.get("index_price"),
                field="ticker.index_price",
                positive=True,
                optional=True,
            ),
            funding_rate=parse_decimal(
                ticker.get("funding_rate"),
                field="ticker.funding_rate",
                optional=True,
            ),
            open_interest=parse_decimal(
                ticker.get("total_size"),
                field="ticker.total_size",
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
