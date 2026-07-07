from datetime import datetime
from decimal import Decimal
from typing import Any

from app.candles.models import (
    CandleBatch,
    CandleInterval,
    CandleRole,
    CandleSource,
    OhlcvCandle,
)


def candle_to_dict(candle: OhlcvCandle) -> dict[str, Any]:
    return {
        "source": candle.source.value,
        "role": candle.role.value,
        "category": candle.category,
        "symbol": candle.symbol,
        "interval": candle.interval.value,
        "open_time": candle.open_time.isoformat(),
        "close_time": candle.close_time.isoformat(),
        "open_price": str(candle.open_price),
        "high_price": str(candle.high_price),
        "low_price": str(candle.low_price),
        "close_price": str(candle.close_price),
        "volume": str(candle.volume),
        "turnover": str(candle.turnover),
    }


def batch_to_payload_data(batch: CandleBatch) -> dict[str, Any]:
    return {
        "source": batch.source.value,
        "role": batch.role.value,
        "category": batch.category,
        "symbol": batch.symbol,
        "interval": batch.interval.value,
        "fetched_at": batch.fetched_at.isoformat(),
        "candles": [candle_to_dict(candle) for candle in batch.candles],
    }


def batch_from_payload_data(data: dict[str, Any]) -> CandleBatch:
    raw_candles = data.get("candles")
    if not isinstance(raw_candles, list):
        raise ValueError("candles must be a list")

    source = CandleSource(str(data.get("source")))
    role = CandleRole(str(data.get("role")))
    category = str(data.get("category", ""))
    symbol = str(data.get("symbol", ""))
    interval = CandleInterval(str(data.get("interval")))
    fetched_at = datetime.fromisoformat(str(data.get("fetched_at")))

    candles: list[OhlcvCandle] = []
    for raw in raw_candles:
        if not isinstance(raw, dict):
            raise ValueError("candle item must be an object")
        candles.append(
            OhlcvCandle(
                source=CandleSource(str(raw.get("source"))),
                role=CandleRole(str(raw.get("role"))),
                category=str(raw.get("category", "")),
                symbol=str(raw.get("symbol", "")),
                interval=CandleInterval(str(raw.get("interval"))),
                open_time=datetime.fromisoformat(str(raw.get("open_time"))),
                close_time=datetime.fromisoformat(str(raw.get("close_time"))),
                open_price=Decimal(str(raw.get("open_price"))),
                high_price=Decimal(str(raw.get("high_price"))),
                low_price=Decimal(str(raw.get("low_price"))),
                close_price=Decimal(str(raw.get("close_price"))),
                volume=Decimal(str(raw.get("volume"))),
                turnover=Decimal(str(raw.get("turnover"))),
            )
        )

    return CandleBatch(
        source=source,
        role=role,
        category=category,
        symbol=symbol,
        interval=interval,
        fetched_at=fetched_at,
        candles=tuple(candles),
    )
