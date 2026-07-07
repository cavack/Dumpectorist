from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from app.adapters.benchmark_models import BenchmarkBookLevel
from app.adapters.parsers import ParserError


def require_object(value: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ParserError(f"{label} must be an object")
    return value


def require_list(value: Any, *, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ParserError(f"{label} must be a list")
    return value


def require_text(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ParserError(f"{field} must be a non-empty string")
    return value.strip()


def parse_decimal(
    value: Any,
    *,
    field: str,
    positive: bool = False,
    non_negative: bool = False,
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
    if non_negative and parsed < 0:
        raise ParserError(f"{field} must be non-negative")
    return parsed


def parse_epoch_ms(value: Any, *, field: str, optional: bool = False) -> datetime | None:
    if value in (None, "") and optional:
        return None
    if isinstance(value, bool):
        raise ParserError(f"{field} must be an integer timestamp")
    try:
        milliseconds = int(value)
    except (TypeError, ValueError) as error:
        raise ParserError(f"{field} must be an integer timestamp") from error
    if milliseconds <= 0:
        raise ParserError(f"{field} must be positive")
    return datetime.fromtimestamp(milliseconds / 1000, tz=timezone.utc)


def parse_epoch_seconds(
    value: Any,
    *,
    field: str,
    optional: bool = False,
) -> datetime | None:
    if value in (None, "") and optional:
        return None
    if isinstance(value, bool):
        raise ParserError(f"{field} must be a timestamp")
    try:
        seconds = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ParserError(f"{field} must be a timestamp") from error
    if not seconds.is_finite() or seconds <= 0:
        raise ParserError(f"{field} must be positive")
    return datetime.fromtimestamp(float(seconds), tz=timezone.utc)


def parse_sequence_book(
    rows: Any,
    *,
    side: str,
    quantity_multiplier: Decimal = Decimal("1"),
) -> tuple[BenchmarkBookLevel, ...]:
    items = require_list(rows, label=side)
    if not items:
        raise ParserError(f"{side} must not be empty")

    levels: list[BenchmarkBookLevel] = []
    for row in items:
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            raise ParserError(f"{side} level must contain price and quantity")
        price = parse_decimal(row[0], field=f"{side}.price", positive=True)
        quantity = parse_decimal(row[1], field=f"{side}.quantity", positive=True)
        levels.append(
            BenchmarkBookLevel(
                price=price,
                quantity=quantity * quantity_multiplier,
            )
        )

    levels.sort(key=lambda item: item.price, reverse=side == "bids")
    return tuple(levels)


def parse_object_book(
    rows: Any,
    *,
    side: str,
    price_field: str,
    quantity_field: str,
    quantity_multiplier: Decimal = Decimal("1"),
    absolute_quantity: bool = False,
) -> tuple[BenchmarkBookLevel, ...]:
    items = require_list(rows, label=side)
    if not items:
        raise ParserError(f"{side} must not be empty")

    levels: list[BenchmarkBookLevel] = []
    for row in items:
        item = require_object(row, label=f"{side} level")
        price = parse_decimal(item.get(price_field), field=f"{side}.{price_field}", positive=True)
        quantity = parse_decimal(
            item.get(quantity_field),
            field=f"{side}.{quantity_field}",
        )
        if absolute_quantity:
            quantity = abs(quantity)
        if quantity <= 0:
            raise ParserError(f"{side}.{quantity_field} must be positive")
        levels.append(
            BenchmarkBookLevel(
                price=price,
                quantity=quantity * quantity_multiplier,
            )
        )

    levels.sort(key=lambda item: item.price, reverse=side == "bids")
    return tuple(levels)


def calculate_book_metrics(
    bids: tuple[BenchmarkBookLevel, ...],
    asks: tuple[BenchmarkBookLevel, ...],
) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal, Decimal]:
    if not bids or not asks:
        raise ParserError("order book must contain bids and asks")
    best_bid = bids[0].price
    best_ask = asks[0].price
    if best_bid >= best_ask:
        raise ParserError("order book is crossed or locked")

    spread = best_ask - best_bid
    mid_price = (best_bid + best_ask) / Decimal("2")
    spread_bps = (spread / mid_price) * Decimal("10000")
    bid_depth_quote = sum(
        (level.price * level.quantity for level in bids),
        start=Decimal("0"),
    )
    ask_depth_quote = sum(
        (level.price * level.quantity for level in asks),
        start=Decimal("0"),
    )
    return best_bid, best_ask, spread, spread_bps, bid_depth_quote, ask_depth_quote
