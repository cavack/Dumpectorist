from decimal import Decimal, InvalidOperation
from typing import Any

from app.adapters.lbank_models import (
    LBankBookLevel,
    LBankInstrument,
    LBankMarketQuote,
    LBankOrderBook,
)
from app.adapters.parsers import ParserError


def _items(payload: Any, *, label: str) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return payload["data"]
    raise ParserError(f"{label} payload must be a list")


def _mapping(value: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ParserError(f"{label} item must be an object")
    return value


def _text(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ParserError(f"{field} must be a non-empty string")
    return value.strip()


def _decimal(
    value: Any,
    *,
    field: str,
    positive: bool = False,
    optional: bool = False,
) -> Decimal | None:
    if value in (None, "") and optional:
        return None
    if isinstance(value, bool):
        raise ParserError(f"{field} must be numeric")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ParserError(f"{field} must be numeric") from error
    if not parsed.is_finite():
        raise ParserError(f"{field} must be finite")
    if positive and parsed <= 0:
        raise ParserError(f"{field} must be positive")
    return parsed


def parse_instruments(payload: Any) -> tuple[LBankInstrument, ...]:
    instruments: list[LBankInstrument] = []
    for raw in _items(payload, label="instrument"):
        item = _mapping(raw, label="instrument")
        instruments.append(
            LBankInstrument(
                symbol=_text(item.get("symbol"), field="symbol"),
                base_currency=_text(item.get("baseCurrency"), field="baseCurrency"),
                price_currency=_text(item.get("priceCurrency"), field="priceCurrency"),
                clear_currency=_text(item.get("clearCurrency"), field="clearCurrency"),
                price_tick=_decimal(
                    item.get("priceTick"),
                    field="priceTick",
                    positive=True,
                ),
                volume_tick=_decimal(
                    item.get("volumeTick"),
                    field="volumeTick",
                    positive=True,
                ),
                volume_multiple=_decimal(
                    item.get("volumeMultiple"),
                    field="volumeMultiple",
                    positive=True,
                ),
                min_order_volume=_decimal(
                    item.get("minOrderVolume"),
                    field="minOrderVolume",
                    positive=True,
                    optional=True,
                ),
                min_order_cost=_decimal(
                    item.get("minOrderCost"),
                    field="minOrderCost",
                    positive=True,
                    optional=True,
                ),
            )
        )
    if not instruments:
        raise ParserError("instrument payload is empty")
    return tuple(instruments)


def parse_market_quotes(payload: Any) -> tuple[LBankMarketQuote, ...]:
    quotes: list[LBankMarketQuote] = []
    for raw in _items(payload, label="marketData"):
        item = _mapping(raw, label="marketData")
        quotes.append(
            LBankMarketQuote(
                symbol=_text(item.get("symbol"), field="symbol"),
                last_price=_decimal(
                    item.get("lastPrice"),
                    field="lastPrice",
                    positive=True,
                ),
                marked_price=_decimal(
                    item.get("markedPrice"),
                    field="markedPrice",
                    positive=True,
                ),
                funding_rate=_decimal(
                    item.get("prePositionFeeRate"),
                    field="prePositionFeeRate",
                    optional=True,
                ),
                volume_24h=_decimal(
                    item.get("volume"),
                    field="volume",
                    optional=True,
                ),
                turnover_24h=_decimal(
                    item.get("turnover"),
                    field="turnover",
                    optional=True,
                ),
            )
        )
    if not quotes:
        raise ParserError("marketData payload is empty")
    return tuple(quotes)


def _book_levels(value: Any, *, side: str) -> tuple[LBankBookLevel, ...]:
    if not isinstance(value, list) or not value:
        raise ParserError(f"{side} must be a non-empty list")

    levels: list[LBankBookLevel] = []
    for raw in value:
        item = _mapping(raw, label=side)
        orders = item.get("orders")
        if orders is not None and (isinstance(orders, bool) or not isinstance(orders, int)):
            raise ParserError(f"{side}.orders must be an integer")
        if isinstance(orders, int) and orders < 0:
            raise ParserError(f"{side}.orders must be non-negative")
        levels.append(
            LBankBookLevel(
                price=_decimal(item.get("price"), field=f"{side}.price", positive=True),
                volume=_decimal(item.get("volume"), field=f"{side}.volume", positive=True),
                orders=orders,
            )
        )

    reverse = side == "bids"
    levels.sort(key=lambda level: level.price, reverse=reverse)
    return tuple(levels)


def parse_order_book(payload: Any, *, expected_symbol: str) -> LBankOrderBook:
    item = _mapping(payload, label="marketOrder")
    if isinstance(item.get("data"), dict):
        item = item["data"]

    symbol = _text(item.get("symbol"), field="symbol")
    if symbol.casefold() != expected_symbol.strip().casefold():
        raise ParserError("order-book symbol does not match requested symbol")

    bids = _book_levels(item.get("bids"), side="bids")
    asks = _book_levels(item.get("asks"), side="asks")
    if bids[0].price >= asks[0].price:
        raise ParserError("order book is crossed or locked")

    return LBankOrderBook(symbol=symbol, bids=bids, asks=asks)


def find_symbol(items: tuple[Any, ...], symbol: str) -> Any:
    normalized = symbol.strip().casefold()
    if not normalized:
        raise ParserError("symbol is required")
    for item in items:
        if item.symbol.casefold() == normalized:
            return item
    raise ParserError(f"symbol not found: {symbol.strip()}")
