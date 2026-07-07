from decimal import Decimal

from app.adapters.lbank_models import LBankBookLevel, LBankExecutionSnapshot
from app.execution.liquidity_models import (
    DepthBandResult,
    ExecutionReadiness,
    LiquidityAssessment,
    LiquidityRules,
    OrderRecommendation,
    OrderSide,
    SlippageEstimate,
)


BPS = Decimal("10000")


def assess_lbank_liquidity(
    snapshot: LBankExecutionSnapshot,
    *,
    rules: LiquidityRules | None = None,
) -> LiquidityAssessment:
    active = rules or LiquidityRules()
    _validate_book_order(snapshot)
    mid = snapshot.executable_mid_price

    depth_bands = tuple(
        _depth_band(snapshot, mid=mid, band_bps=band)
        for band in active.depth_bands_bps
    )
    sell = tuple(
        _estimate_slippage(
            snapshot.order_book.bids,
            side=OrderSide.SELL,
            requested_quote=size,
        )
        for size in active.order_sizes_quote
    )
    buy = tuple(
        _estimate_slippage(
            snapshot.order_book.asks,
            side=OrderSide.BUY,
            requested_quote=size,
        )
        for size in active.order_sizes_quote
    )

    inner = depth_bands[0]
    outer = depth_bands[-1]
    bid_growth = _growth(outer.bid_depth_quote, inner.bid_depth_quote)
    ask_growth = _growth(outer.ask_depth_quote, inner.ask_depth_quote)
    reasons: list[str] = []
    warnings: list[str] = []

    if inner.bid_depth_quote < active.minimum_inner_bid_depth_quote:
        reasons.append("INNER_BID_DEPTH_INSUFFICIENT")
    if inner.ask_depth_quote < active.minimum_inner_ask_depth_quote:
        reasons.append("INNER_ASK_DEPTH_INSUFFICIENT")
    if bid_growth is None or bid_growth < active.minimum_outer_to_inner_growth:
        warnings.append("BID_LIQUIDITY_CLIFF")
    if ask_growth is None or ask_growth < active.minimum_outer_to_inner_growth:
        warnings.append("ASK_LIQUIDITY_CLIFF")

    sell_unfilled = _unfilled_fraction(sell[-1])
    buy_unfilled = _unfilled_fraction(buy[-1])
    if sell_unfilled > active.maximum_unfilled_fraction:
        reasons.append("LARGE_SELL_SIZE_NOT_FILLABLE")
    if buy_unfilled > active.maximum_unfilled_fraction:
        reasons.append("LARGE_BUY_SIZE_NOT_FILLABLE")

    small_sell = sell[0]
    if small_sell.slippage_bps is None:
        reasons.append("SMALL_SELL_SLIPPAGE_UNAVAILABLE")
    elif small_sell.slippage_bps > active.max_limit_slippage_bps:
        reasons.append("SMALL_SELL_SLIPPAGE_EXCESSIVE")

    if any(reason.endswith("NOT_FILLABLE") for reason in reasons) or any(
        reason.endswith("EXCESSIVE") for reason in reasons
    ):
        readiness = ExecutionReadiness.NO_TRADE
        recommendation = OrderRecommendation.NO_ORDER
    elif reasons:
        readiness = ExecutionReadiness.EXECUTION_PENDING
        recommendation = OrderRecommendation.POST_ONLY_REQUIRED
    elif warnings:
        readiness = ExecutionReadiness.EXECUTION_PENDING
        recommendation = OrderRecommendation.POST_ONLY_REQUIRED
    elif _requires_limit(sell + buy, active):
        readiness = ExecutionReadiness.EXECUTABLE
        recommendation = OrderRecommendation.LIMIT_PREFERRED
        warnings.append("MARKET_ORDER_SLIPPAGE_RISK")
    else:
        readiness = ExecutionReadiness.EXECUTABLE
        recommendation = OrderRecommendation.MARKET_ALLOWED

    return LiquidityAssessment(
        symbol=snapshot.symbol,
        readiness=readiness,
        recommendation=recommendation,
        mid_price=mid,
        depth_bands=depth_bands,
        sell_slippage=sell,
        buy_slippage=buy,
        bid_outer_to_inner_growth=bid_growth,
        ask_outer_to_inner_growth=ask_growth,
        reasons=tuple(reasons),
        warnings=tuple(warnings),
    )


def _validate_book_order(snapshot: LBankExecutionSnapshot) -> None:
    bid_prices = tuple(level.price for level in snapshot.order_book.bids)
    ask_prices = tuple(level.price for level in snapshot.order_book.asks)
    if bid_prices != tuple(sorted(bid_prices, reverse=True)):
        raise ValueError("bid levels must be sorted from highest to lowest")
    if ask_prices != tuple(sorted(ask_prices)):
        raise ValueError("ask levels must be sorted from lowest to highest")


def _depth_band(
    snapshot: LBankExecutionSnapshot,
    *,
    mid: Decimal,
    band_bps: Decimal,
) -> DepthBandResult:
    fraction = band_bps / BPS
    bid_floor = mid * (Decimal("1") - fraction)
    ask_ceiling = mid * (Decimal("1") + fraction)
    bid_depth = sum(
        (level.price * level.volume for level in snapshot.order_book.bids if level.price >= bid_floor),
        Decimal("0"),
    )
    ask_depth = sum(
        (level.price * level.volume for level in snapshot.order_book.asks if level.price <= ask_ceiling),
        Decimal("0"),
    )
    return DepthBandResult(
        band_bps=band_bps,
        bid_depth_quote=bid_depth,
        ask_depth_quote=ask_depth,
    )


def _estimate_slippage(
    levels: tuple[LBankBookLevel, ...],
    *,
    side: OrderSide,
    requested_quote: Decimal,
) -> SlippageEstimate:
    reference = levels[0].price
    target_base = requested_quote / reference
    remaining_base = target_base
    filled_base = Decimal("0")
    actual_quote = Decimal("0")
    worst_price: Decimal | None = None

    for level in levels:
        if remaining_base <= 0:
            break
        quantity = min(level.volume, remaining_base)
        if quantity <= 0:
            continue
        filled_base += quantity
        actual_quote += quantity * level.price
        remaining_base -= quantity
        worst_price = level.price

    filled_reference_quote = filled_base * reference
    unfilled_reference_quote = max(Decimal("0"), requested_quote - filled_reference_quote)
    if filled_base == 0:
        return SlippageEstimate(
            side=side,
            requested_quote=requested_quote,
            filled_quote=Decimal("0"),
            unfilled_quote=requested_quote,
            average_price=None,
            worst_price=None,
            slippage_bps=None,
        )

    average = actual_quote / filled_base
    if side == OrderSide.SELL:
        slippage = max(Decimal("0"), (reference - average) / reference * BPS)
    else:
        slippage = max(Decimal("0"), (average - reference) / reference * BPS)
    return SlippageEstimate(
        side=side,
        requested_quote=requested_quote,
        filled_quote=filled_reference_quote,
        unfilled_quote=unfilled_reference_quote,
        average_price=average,
        worst_price=worst_price,
        slippage_bps=slippage,
    )


def _growth(outer: Decimal, inner: Decimal) -> Decimal | None:
    if inner <= 0:
        return None
    return outer / inner


def _unfilled_fraction(estimate: SlippageEstimate) -> Decimal:
    return estimate.unfilled_quote / estimate.requested_quote


def _requires_limit(
    estimates: tuple[SlippageEstimate, ...],
    rules: LiquidityRules,
) -> bool:
    return any(
        estimate.slippage_bps is not None
        and estimate.slippage_bps > rules.max_market_slippage_bps
        for estimate in estimates
    )
