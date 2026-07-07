from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.adapters.lbank_models import (
    LBankBookLevel,
    LBankExecutionSnapshot,
    LBankInstrument,
    LBankMarketQuote,
    LBankOrderBook,
)
from app.execution.liquidity import assess_lbank_liquidity
from app.execution.liquidity_models import (
    ExecutionReadiness,
    LiquidityRules,
    OrderRecommendation,
    OrderSide,
)


NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


def level(price: str, volume: str) -> LBankBookLevel:
    return LBankBookLevel(price=Decimal(price), volume=Decimal(volume))


def snapshot(*, scale: str = "1", flat_outer: bool = False) -> LBankExecutionSnapshot:
    multiplier = Decimal(scale)
    outer = Decimal("0.01") if flat_outer else multiplier
    bids = (
        level("99.9", str(Decimal("4") * multiplier)),
        level("99.8", str(Decimal("6") * multiplier)),
        level("99.5", str(Decimal("10") * outer)),
        level("99", str(Decimal("20") * outer)),
    )
    asks = (
        level("100.1", str(Decimal("4") * multiplier)),
        level("100.2", str(Decimal("6") * multiplier)),
        level("100.5", str(Decimal("10") * outer)),
        level("101", str(Decimal("20") * outer)),
    )
    instrument = LBankInstrument(
        symbol="BTC_USDT",
        base_currency="BTC",
        price_currency="USDT",
        clear_currency="USDT",
        price_tick=Decimal("0.1"),
        volume_tick=Decimal("0.001"),
        volume_multiple=Decimal("1"),
        min_order_volume=Decimal("0.001"),
        min_order_cost=Decimal("5"),
    )
    quote = LBankMarketQuote(
        symbol="BTC_USDT",
        last_price=Decimal("100"),
        marked_price=Decimal("100"),
        funding_rate=Decimal("0.0001"),
        volume_24h=Decimal("100000"),
        turnover_24h=Decimal("10000000"),
    )
    book = LBankOrderBook(symbol="BTC_USDT", bids=bids, asks=asks)
    return LBankExecutionSnapshot(
        source="LBANK",
        product_group="USDT_PERPETUAL",
        symbol="BTC_USDT",
        received_at=NOW,
        latency_ms=100,
        instrument=instrument,
        quote=quote,
        order_book=book,
        spread=Decimal("0.2"),
        spread_bps=Decimal("20"),
        bid_depth_quote=sum(item.price * item.volume for item in bids),
        ask_depth_quote=sum(item.price * item.volume for item in asks),
    )


def test_depth_bands_and_three_size_buckets_are_calculated():
    report = assess_lbank_liquidity(snapshot())

    assert [item.band_bps for item in report.depth_bands] == [
        Decimal("25"),
        Decimal("50"),
        Decimal("100"),
    ]
    assert report.depth_bands[0].bid_depth_quote == Decimal("998.4")
    assert report.depth_bands[0].ask_depth_quote == Decimal("1001.6")
    assert len(report.sell_slippage) == 3
    assert len(report.buy_slippage) == 3
    assert all(item.side == OrderSide.SELL for item in report.sell_slippage)
    assert all(item.fully_filled for item in report.sell_slippage)


def test_deep_book_can_allow_market_execution():
    report = assess_lbank_liquidity(snapshot(scale="5"))

    assert report.readiness == ExecutionReadiness.EXECUTABLE
    assert report.recommendation == OrderRecommendation.MARKET_ALLOWED
    assert report.reasons == ()


def test_thin_book_blocks_execution_and_market_order():
    report = assess_lbank_liquidity(snapshot(scale="0.01"))

    assert report.readiness == ExecutionReadiness.NO_TRADE
    assert report.recommendation == OrderRecommendation.NO_ORDER
    assert "LARGE_SELL_SIZE_NOT_FILLABLE" in report.reasons
    assert "LARGE_BUY_SIZE_NOT_FILLABLE" in report.reasons


def test_liquidity_cliff_requires_post_only_behavior():
    rules = LiquidityRules(
        minimum_inner_bid_depth_quote=Decimal("100"),
        minimum_inner_ask_depth_quote=Decimal("100"),
        maximum_unfilled_fraction=Decimal("1"),
    )
    report = assess_lbank_liquidity(snapshot(scale="5", flat_outer=True), rules=rules)

    assert report.readiness == ExecutionReadiness.EXECUTION_PENDING
    assert report.recommendation == OrderRecommendation.POST_ONLY_REQUIRED
    assert "BID_LIQUIDITY_CLIFF" in report.warnings
    assert "ASK_LIQUIDITY_CLIFF" in report.warnings


def test_slippage_above_market_threshold_prefers_limit():
    rules = LiquidityRules(
        max_market_slippage_bps=Decimal("0.1"),
        max_limit_slippage_bps=Decimal("100"),
        minimum_inner_bid_depth_quote=Decimal("100"),
        minimum_inner_ask_depth_quote=Decimal("100"),
        minimum_outer_to_inner_growth=Decimal("1"),
        maximum_unfilled_fraction=Decimal("1"),
    )
    report = assess_lbank_liquidity(snapshot(), rules=rules)

    assert report.readiness == ExecutionReadiness.EXECUTABLE
    assert report.recommendation == OrderRecommendation.LIMIT_PREFERRED
    assert "MARKET_ORDER_SLIPPAGE_RISK" in report.warnings


def test_unsorted_book_is_rejected_before_metrics_are_calculated():
    original = snapshot()
    reversed_book = LBankOrderBook(
        symbol=original.symbol,
        bids=tuple(reversed(original.order_book.bids)),
        asks=original.order_book.asks,
    )
    values = vars(original).copy()
    values["order_book"] = reversed_book
    values["spread"] = reversed_book.best_ask.price - reversed_book.best_bid.price
    values["spread_bps"] = Decimal("110")

    with pytest.raises(ValueError, match="bid levels must be sorted"):
        assess_lbank_liquidity(LBankExecutionSnapshot(**values))


def test_rules_require_ordered_bands_and_three_sizes():
    with pytest.raises(ValueError, match="unique and increasing"):
        LiquidityRules(depth_bands_bps=(Decimal("50"), Decimal("25")))
    with pytest.raises(ValueError, match="small, medium, and large"):
        LiquidityRules(order_sizes_quote=(Decimal("100"), Decimal("500")))
