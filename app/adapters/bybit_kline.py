from collections.abc import Callable
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Protocol

from app.adapters.benchmark_utils import (
    parse_decimal,
    parse_epoch_ms,
    require_list,
    require_object,
    require_text,
)
from app.adapters.http_client import HttpClient
from app.adapters.models import AdapterHealth, AdapterPayload, AdapterState
from app.adapters.parsers import ParserError
from app.candles.health import CandleFreshnessState, evaluate_candle_freshness
from app.candles.models import (
    CandleBatch,
    CandleInterval,
    CandleRole,
    CandleSource,
    OhlcvCandle,
)
from app.candles.serialization import batch_to_payload_data


class JsonValueClient(Protocol):
    async def get_json_value(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Return a decoded JSON value."""


class BybitKlineAdapter:
    default_base_url = "https://api.bybit.com"

    def __init__(
        self,
        *,
        symbol: str,
        interval: CandleInterval,
        category: str = "linear",
        limit: int = 200,
        base_url: str = default_base_url,
        client: JsonValueClient | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        normalized_symbol = symbol.strip().upper()
        normalized_category = category.strip().lower()
        normalized_url = base_url.rstrip("/")
        if not normalized_symbol:
            raise ValueError("symbol is required")
        if normalized_category not in {"spot", "linear", "inverse"}:
            raise ValueError("unsupported Bybit kline category")
        if limit < 1 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000")
        if not normalized_url.startswith("https://"):
            raise ValueError("base_url must use HTTPS")

        self.symbol = normalized_symbol
        self.interval = interval
        self.category = normalized_category
        self.limit = limit
        self.base_url = normalized_url
        self.client = client or HttpClient()
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.name = f"bybit-kline-{interval.label}"

    def _url(self) -> str:
        return f"{self.base_url}/v5/market/kline"

    def _now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("clock must return a timezone-aware datetime")
        return value

    def _parse_row(self, raw: Any, *, fetched_at: datetime) -> OhlcvCandle | None:
        if not isinstance(raw, list) or len(raw) < 7:
            raise ParserError("kline row must contain seven values")
        open_time = parse_epoch_ms(raw[0], field="kline.startTime")
        if open_time is None:
            raise ParserError("kline.startTime is required")
        close_time = open_time + self.interval.duration
        if close_time > fetched_at:
            return None

        return OhlcvCandle(
            source=CandleSource.BYBIT,
            role=CandleRole.STRUCTURE_DATA,
            category=self.category,
            symbol=self.symbol,
            interval=self.interval,
            open_time=open_time,
            close_time=close_time,
            open_price=parse_decimal(raw[1], field="kline.openPrice", positive=True),
            high_price=parse_decimal(raw[2], field="kline.highPrice", positive=True),
            low_price=parse_decimal(raw[3], field="kline.lowPrice", positive=True),
            close_price=parse_decimal(raw[4], field="kline.closePrice", positive=True),
            volume=parse_decimal(raw[5], field="kline.volume", non_negative=True),
            turnover=parse_decimal(raw[6], field="kline.turnover", non_negative=True),
        )

    async def fetch_batch(self) -> CandleBatch:
        payload = await self.client.get_json_value(
            self._url(),
            params={
                "category": self.category,
                "symbol": self.symbol,
                "interval": self.interval.value,
                "limit": self.limit,
            },
        )
        root = require_object(payload, label="kline")
        if root.get("retCode") != 0:
            raise ParserError("Bybit kline endpoint reported failure")
        result = require_object(root.get("result"), label="kline.result")
        result_symbol = require_text(result.get("symbol"), field="kline.result.symbol")
        result_category = require_text(
            result.get("category"),
            field="kline.result.category",
        ).lower()
        if result_symbol.upper() != self.symbol:
            raise ParserError("Bybit kline symbol mismatch")
        if result_category != self.category:
            raise ParserError("Bybit kline category mismatch")

        fetched_at = self._now()
        raw_rows = require_list(result.get("list"), label="kline.result.list")
        candles = [
            candle
            for raw in raw_rows
            if (candle := self._parse_row(raw, fetched_at=fetched_at)) is not None
        ]
        candles.sort(key=lambda candle: candle.open_time)

        return CandleBatch(
            source=CandleSource.BYBIT,
            role=CandleRole.STRUCTURE_DATA,
            category=self.category,
            symbol=self.symbol,
            interval=self.interval,
            fetched_at=fetched_at,
            candles=tuple(candles),
        )

    async def load(self) -> AdapterPayload:
        started = perf_counter()
        try:
            batch = await self.fetch_batch()
            freshness = evaluate_candle_freshness(batch, now=batch.fetched_at)
        except Exception as error:
            state = (
                AdapterState.DEGRADED
                if isinstance(error, (ParserError, ValueError))
                else AdapterState.DOWN
            )
            return AdapterPayload(
                name=self.name,
                data={
                    "source": CandleSource.BYBIT.value,
                    "role": CandleRole.STRUCTURE_DATA.value,
                    "category": self.category,
                    "symbol": self.symbol,
                    "interval": self.interval.value,
                    "status": "DATA_DEGRADED",
                    "candles": [],
                },
                health=AdapterHealth(
                    name=self.name,
                    state=state,
                    latency_ms=round((perf_counter() - started) * 1000),
                    message=type(error).__name__,
                ),
            )

        data = batch_to_payload_data(batch)
        data["status"] = freshness.state.value
        data["freshness_age_seconds"] = freshness.age_seconds
        data["freshness_reasons"] = list(freshness.reasons)
        state = (
            AdapterState.OK
            if freshness.state == CandleFreshnessState.OK
            else AdapterState.DEGRADED
        )
        return AdapterPayload(
            name=self.name,
            data=data,
            health=AdapterHealth(
                name=self.name,
                state=state,
                latency_ms=round((perf_counter() - started) * 1000),
                message=",".join(freshness.reasons),
            ),
        )
