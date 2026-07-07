from asyncio import gather
from collections.abc import Callable
from datetime import datetime, timezone
from decimal import Decimal
from time import perf_counter
from typing import Any, Protocol

from app.adapters.http_client import HttpClient
from app.adapters.lbank_models import LBankExecutionSnapshot
from app.adapters.lbank_parser import (
    find_symbol,
    parse_instruments,
    parse_market_quotes,
    parse_order_book,
)
from app.adapters.models import AdapterHealth, AdapterPayload, AdapterState
from app.adapters.parsers import ParserError


class JsonValueClient(Protocol):
    async def get_json_value(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Return a decoded JSON value."""


class LBankPublicAdapter:
    name = "lbank-perpetual-public"
    default_base_url = "https://lbkperp.lbank.com"

    def __init__(
        self,
        *,
        symbol: str,
        product_group: str = "SwapU",
        depth: int = 20,
        base_url: str = default_base_url,
        client: JsonValueClient | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        normalized_symbol = symbol.strip()
        normalized_group = product_group.strip()
        normalized_url = base_url.rstrip("/")
        if not normalized_symbol:
            raise ValueError("symbol is required")
        if not normalized_group:
            raise ValueError("product_group is required")
        if depth < 1:
            raise ValueError("depth must be positive")
        if not normalized_url.startswith("https://"):
            raise ValueError("base_url must use HTTPS")

        self.symbol = normalized_symbol
        self.product_group = normalized_group
        self.depth = depth
        self.base_url = normalized_url
        self.client = client or HttpClient()
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    async def health(self) -> AdapterHealth:
        started = perf_counter()
        try:
            payload = await self.client.get_json_value(
                self._url("/cfd/openApi/v1/pub/getTime")
            )
            if not isinstance(payload, dict):
                raise ParserError("time payload must be an object")
            if payload.get("success") is False:
                raise ParserError("LBank public endpoint reported failure")
        except Exception as error:
            return AdapterHealth(
                name=self.name,
                state=AdapterState.DOWN,
                latency_ms=round((perf_counter() - started) * 1000),
                message=type(error).__name__,
            )

        return AdapterHealth(
            name=self.name,
            state=AdapterState.OK,
            latency_ms=round((perf_counter() - started) * 1000),
        )

    async def fetch_snapshot(self) -> LBankExecutionSnapshot:
        started = perf_counter()
        instrument_payload, market_payload, book_payload = await gather(
            self.client.get_json_value(
                self._url("/cfd/openApi/v1/pub/instrument"),
                params={"productGroup": self.product_group},
            ),
            self.client.get_json_value(
                self._url("/cfd/openApi/v1/pub/marketData"),
                params={"productGroup": self.product_group},
            ),
            self.client.get_json_value(
                self._url("/cfd/openApi/v1/pub/marketOrder"),
                params={"symbol": self.symbol, "depth": self.depth},
            ),
        )

        instrument = find_symbol(parse_instruments(instrument_payload), self.symbol)
        quote = find_symbol(parse_market_quotes(market_payload), self.symbol)
        order_book = parse_order_book(book_payload, expected_symbol=self.symbol)

        best_bid = order_book.best_bid.price
        best_ask = order_book.best_ask.price
        spread = best_ask - best_bid
        mid_price = (best_bid + best_ask) / Decimal("2")
        spread_bps = (spread / mid_price) * Decimal("10000")
        multiplier = instrument.volume_multiple
        bid_depth_quote = sum(
            (level.price * level.volume * multiplier for level in order_book.bids),
            start=Decimal("0"),
        )
        ask_depth_quote = sum(
            (level.price * level.volume * multiplier for level in order_book.asks),
            start=Decimal("0"),
        )

        received_at = self.clock()
        if received_at.tzinfo is None or received_at.utcoffset() is None:
            raise ValueError("clock must return a timezone-aware datetime")

        return LBankExecutionSnapshot(
            source="LBank",
            product_group=self.product_group,
            symbol=instrument.symbol,
            received_at=received_at,
            latency_ms=round((perf_counter() - started) * 1000),
            instrument=instrument,
            quote=quote,
            order_book=order_book,
            spread=spread,
            spread_bps=spread_bps,
            bid_depth_quote=bid_depth_quote,
            ask_depth_quote=ask_depth_quote,
        )

    async def load(self) -> AdapterPayload:
        try:
            snapshot = await self.fetch_snapshot()
        except Exception as error:
            state = AdapterState.DEGRADED if isinstance(error, ValueError) else AdapterState.DOWN
            return AdapterPayload(
                name=self.name,
                data={
                    "symbol": self.symbol,
                    "product_group": self.product_group,
                    "status": "DATA_DEGRADED",
                },
                health=AdapterHealth(
                    name=self.name,
                    state=state,
                    message=type(error).__name__,
                ),
            )

        return AdapterPayload(
            name=self.name,
            data={
                "source": snapshot.source,
                "product_group": snapshot.product_group,
                "symbol": snapshot.symbol,
                "received_at": snapshot.received_at.isoformat(),
                "latency_ms": snapshot.latency_ms,
                "last_price": str(snapshot.quote.last_price),
                "marked_price": str(snapshot.quote.marked_price),
                "best_bid": str(snapshot.order_book.best_bid.price),
                "best_ask": str(snapshot.order_book.best_ask.price),
                "spread": str(snapshot.spread),
                "spread_bps": str(snapshot.spread_bps),
                "bid_depth_quote": str(snapshot.bid_depth_quote),
                "ask_depth_quote": str(snapshot.ask_depth_quote),
                "price_tick": str(snapshot.instrument.price_tick),
                "volume_tick": str(snapshot.instrument.volume_tick),
                "min_order_volume": (
                    str(snapshot.instrument.min_order_volume)
                    if snapshot.instrument.min_order_volume is not None
                    else None
                ),
                "status": "OK",
            },
            health=AdapterHealth(
                name=self.name,
                state=AdapterState.OK,
                latency_ms=snapshot.latency_ms,
            ),
        )
