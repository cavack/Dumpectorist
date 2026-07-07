from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum


class ExecutionReadiness(StrEnum):
    EXECUTABLE = "EXECUTABLE"
    EXECUTION_PENDING = "EXECUTION_PENDING"
    DATA_DEGRADED = "DATA_DEGRADED"
    NO_TRADE = "NO_TRADE"


class OrderRecommendation(StrEnum):
    MARKET_ALLOWED = "MARKET_ALLOWED"
    LIMIT_PREFERRED = "LIMIT_PREFERRED"
    POST_ONLY_REQUIRED = "POST_ONLY_REQUIRED"
    NO_ORDER = "NO_ORDER"


class OrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


def finite_decimal(value, *, name: str, minimum: Decimal | None = None) -> Decimal:
    try:
        normalized = value if isinstance(value, Decimal) else Decimal(str(value))
    except Exception as error:
        raise ValueError(f"{name} must be decimal-compatible") from error
    if not normalized.is_finite():
        raise ValueError(f"{name} must be finite")
    if minimum is not None and normalized < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return normalized


@dataclass(frozen=True)
class LiquidityRules:
    depth_bands_bps: tuple[Decimal, ...] = (
        Decimal("25"),
        Decimal("50"),
        Decimal("100"),
    )
    order_sizes_quote: tuple[Decimal, ...] = (
        Decimal("100"),
        Decimal("500"),
        Decimal("1000"),
    )
    max_market_slippage_bps: Decimal = Decimal("12")
    max_limit_slippage_bps: Decimal = Decimal("35")
    minimum_inner_bid_depth_quote: Decimal = Decimal("500")
    minimum_inner_ask_depth_quote: Decimal = Decimal("500")
    minimum_outer_to_inner_growth: Decimal = Decimal("1.50")
    maximum_unfilled_fraction: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        bands = tuple(
            finite_decimal(item, name="depth_band", minimum=Decimal("0.0001"))
            for item in self.depth_bands_bps
        )
        sizes = tuple(
            finite_decimal(item, name="order_size", minimum=Decimal("0.0001"))
            for item in self.order_sizes_quote
        )
        if tuple(sorted(set(bands))) != bands:
            raise ValueError("depth bands must be unique and increasing")
        if tuple(sorted(set(sizes))) != sizes:
            raise ValueError("order sizes must be unique and increasing")
        if len(bands) < 2:
            raise ValueError("at least two depth bands are required")
        if len(sizes) != 3:
            raise ValueError("small, medium, and large order sizes are required")
        for value, name in (
            (self.max_market_slippage_bps, "max_market_slippage_bps"),
            (self.max_limit_slippage_bps, "max_limit_slippage_bps"),
            (self.minimum_inner_bid_depth_quote, "minimum_inner_bid_depth_quote"),
            (self.minimum_inner_ask_depth_quote, "minimum_inner_ask_depth_quote"),
            (self.minimum_outer_to_inner_growth, "minimum_outer_to_inner_growth"),
            (self.maximum_unfilled_fraction, "maximum_unfilled_fraction"),
        ):
            finite_decimal(value, name=name, minimum=Decimal("0"))
        if self.max_limit_slippage_bps < self.max_market_slippage_bps:
            raise ValueError("limit threshold must cover the market threshold")
        if self.maximum_unfilled_fraction > Decimal("1"):
            raise ValueError("maximum_unfilled_fraction must not exceed one")
        object.__setattr__(self, "depth_bands_bps", bands)
        object.__setattr__(self, "order_sizes_quote", sizes)


@dataclass(frozen=True)
class DepthBandResult:
    band_bps: Decimal
    bid_depth_quote: Decimal
    ask_depth_quote: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "band_bps",
            finite_decimal(self.band_bps, name="band_bps", minimum=Decimal("0")),
        )
        object.__setattr__(
            self,
            "bid_depth_quote",
            finite_decimal(
                self.bid_depth_quote,
                name="bid_depth_quote",
                minimum=Decimal("0"),
            ),
        )
        object.__setattr__(
            self,
            "ask_depth_quote",
            finite_decimal(
                self.ask_depth_quote,
                name="ask_depth_quote",
                minimum=Decimal("0"),
            ),
        )


@dataclass(frozen=True)
class SlippageEstimate:
    side: OrderSide
    requested_quote: Decimal
    filled_quote: Decimal
    unfilled_quote: Decimal
    average_price: Decimal | None
    worst_price: Decimal | None
    slippage_bps: Decimal | None

    def __post_init__(self) -> None:
        requested = finite_decimal(
            self.requested_quote,
            name="requested_quote",
            minimum=Decimal("0.0001"),
        )
        filled = finite_decimal(self.filled_quote, name="filled_quote", minimum=Decimal("0"))
        unfilled = finite_decimal(
            self.unfilled_quote,
            name="unfilled_quote",
            minimum=Decimal("0"),
        )
        if abs(requested - filled - unfilled) > Decimal("0.000001"):
            raise ValueError("filled and unfilled quote must reconcile to requested quote")
        if filled == 0 and (self.average_price is not None or self.worst_price is not None):
            raise ValueError("unfilled estimate cannot contain fill prices")
        for value, name in (
            (self.average_price, "average_price"),
            (self.worst_price, "worst_price"),
            (self.slippage_bps, "slippage_bps"),
        ):
            if value is not None:
                finite_decimal(value, name=name, minimum=Decimal("0"))
        object.__setattr__(self, "requested_quote", requested)
        object.__setattr__(self, "filled_quote", filled)
        object.__setattr__(self, "unfilled_quote", unfilled)

    @property
    def fully_filled(self) -> bool:
        return self.unfilled_quote == 0


@dataclass(frozen=True)
class LiquidityAssessment:
    symbol: str
    readiness: ExecutionReadiness
    recommendation: OrderRecommendation
    mid_price: Decimal
    depth_bands: tuple[DepthBandResult, ...]
    sell_slippage: tuple[SlippageEstimate, ...]
    buy_slippage: tuple[SlippageEstimate, ...]
    bid_outer_to_inner_growth: Decimal | None
    ask_outer_to_inner_growth: Decimal | None
    reasons: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        symbol = self.symbol.strip()
        if not symbol:
            raise ValueError("symbol is required")
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(
            self,
            "mid_price",
            finite_decimal(self.mid_price, name="mid_price", minimum=Decimal("0.0001")),
        )
        if not self.depth_bands:
            raise ValueError("depth bands are required")
        if len(self.sell_slippage) != 3 or len(self.buy_slippage) != 3:
            raise ValueError("small, medium, and large slippage estimates are required")
