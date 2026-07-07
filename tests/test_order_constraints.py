from decimal import Decimal

from app.adapters.lbank_models import LBankInstrument
from app.execution.liquidity_models import OrderSide
from app.execution.order_constraints import (
    ExecutionOrderRequest,
    validate_order_constraints,
)


def instrument(**overrides):
    values = {
        "symbol": "MEME_USDT",
        "base_currency": "MEME",
        "price_currency": "USDT",
        "clear_currency": "USDT",
        "price_tick": Decimal("0.0001"),
        "volume_tick": Decimal("1"),
        "volume_multiple": Decimal("1"),
        "min_order_volume": Decimal("10"),
        "min_order_cost": Decimal("5"),
    }
    values.update(overrides)
    return LBankInstrument(**values)


def request(price="0.1000", volume="100"):
    return ExecutionOrderRequest(
        side=OrderSide.SELL,
        price=Decimal(price),
        volume=Decimal(volume),
        post_only=True,
    )


def test_aligned_order_meets_exchange_constraints():
    result = validate_order_constraints(request(), instrument())

    assert result.valid is True
    assert result.quote_cost == Decimal("10.0000")
    assert result.reasons == ()


def test_price_and_volume_tick_mismatches_are_explicit():
    result = validate_order_constraints(
        request(price="0.10005", volume="10.5"),
        instrument(),
    )

    assert result.valid is False
    assert "PRICE_NOT_ALIGNED_TO_TICK" in result.reasons
    assert "VOLUME_NOT_ALIGNED_TO_TICK" in result.reasons


def test_minimum_volume_and_cost_are_hard_constraints():
    result = validate_order_constraints(request(price="0.1000", volume="5"), instrument())

    assert result.valid is False
    assert "ORDER_VOLUME_BELOW_MINIMUM" in result.reasons
    assert "ORDER_COST_BELOW_MINIMUM" in result.reasons


def test_missing_minimum_metadata_is_not_assumed():
    result = validate_order_constraints(
        request(),
        instrument(min_order_volume=None, min_order_cost=None),
    )

    assert result.valid is False
    assert result.reasons == (
        "MIN_ORDER_VOLUME_UNAVAILABLE",
        "MIN_ORDER_COST_UNAVAILABLE",
    )
