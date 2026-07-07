from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


def _finite_decimal(value: Decimal, *, name: str) -> Decimal:
    if not isinstance(value, Decimal):
        try:
            value = Decimal(str(value))
        except Exception as error:
            raise ValueError(f"{name} must be decimal-compatible") from error
    if not value.is_finite():
        raise ValueError(f"{name} must be finite")
    return value


def _positive_decimal(value: Decimal, *, name: str) -> Decimal:
    value = _finite_decimal(value, name=name)
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _non_negative_decimal(value: Decimal, *, name: str) -> Decimal:
    value = _finite_decimal(value, name=name)
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _required_text(value: str, *, name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} is required")
    return normalized


@dataclass(frozen=True)
class LBankInstrument:
    symbol: str
    base_currency: str
    price_currency: str
    clear_currency: str
    price_tick: Decimal
    volume_tick: Decimal
    volume_multiple: Decimal
    min_order_volume: Decimal | None = None
    min_order_cost: Decimal | None = None

    def __post_init__(self) -> None:
        for name in ("symbol", "base_currency", "price_currency", "clear_currency"):
            object.__setattr__(self, name, _required_text(getattr(self, name), name=name))
        for name in ("price_tick", "volume_tick", "volume_multiple"):
            object.__setattr__(
                self,
                name,
                _positive_decimal(getattr(self, name), name=name),
            )
        for name in ("min_order_volume", "min_order_cost"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _positive_decimal(value, name=name))


@dataclass(frozen=True)
class LBankMarketQuote:
    symbol: str
    last_price: Decimal
    marked_price: Decimal
    funding_rate: Decimal | None
    volume_24h: Decimal | None
    turnover_24h: Decimal | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", _required_text(self.symbol, name="symbol"))
        object.__setattr__(
            self,
            "last_price",
            _positive_decimal(self.last_price, name="last_price"),
        )
        object.__setattr__(
            self,
            "marked_price",
            _positive_decimal(self.marked_price, name="marked_price"),
        )
        if self.funding_rate is not None:
            object.__setattr__(
                self,
                "funding_rate",
                _finite_decimal(self.funding_rate, name="funding_rate"),
            )
        for name in ("volume_24h", "turnover_24h"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _non_negative_decimal(value, name=name))


@dataclass(frozen=True)
class LBankBookLevel:
    price: Decimal
    volume: Decimal
    orders: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "price", _positive_decimal(self.price, name="price"))
        object.__setattr__(self, "volume", _positive_decimal(self.volume, name="volume"))
        if self.orders is not None:
            if isinstance(self.orders, bool) or not isinstance(self.orders, int):
                raise ValueError("orders must be an integer")
            if self.orders < 0:
                raise ValueError("orders must be non-negative")


@dataclass(frozen=True)
class LBankOrderBook:
    symbol: str
    bids: tuple[LBankBookLevel, ...]
    asks: tuple[LBankBookLevel, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", _required_text(self.symbol, name="symbol"))
        if not self.bids or not self.asks:
            raise ValueError("order book requires bids and asks")
        if self.bids[0].price >= self.asks[0].price:
            raise ValueError("order book must not be crossed or locked")

    @property
    def best_bid(self) -> LBankBookLevel:
        return self.bids[0]

    @property
    def best_ask(self) -> LBankBookLevel:
        return self.asks[0]


@dataclass(frozen=True)
class LBankExecutionSnapshot:
    source: str
    product_group: str
    symbol: str
    received_at: datetime
    latency_ms: int
    instrument: LBankInstrument
    quote: LBankMarketQuote
    order_book: LBankOrderBook
    spread: Decimal
    spread_bps: Decimal
    bid_depth_quote: Decimal
    ask_depth_quote: Decimal

    def __post_init__(self) -> None:
        source = _required_text(self.source, name="source")
        product_group = _required_text(self.product_group, name="product_group")
        symbol = _required_text(self.symbol, name="symbol")
        if self.received_at.tzinfo is None or self.received_at.utcoffset() is None:
            raise ValueError("received_at must be timezone-aware")
        if isinstance(self.latency_ms, bool) or not isinstance(self.latency_ms, int):
            raise ValueError("latency_ms must be an integer")
        if self.latency_ms < 0:
            raise ValueError("latency_ms must be non-negative")

        expected = symbol.casefold()
        for name, value in (
            ("instrument", self.instrument.symbol),
            ("quote", self.quote.symbol),
            ("order_book", self.order_book.symbol),
        ):
            if value.casefold() != expected:
                raise ValueError(f"{name} symbol mismatch")

        expected_spread = self.order_book.best_ask.price - self.order_book.best_bid.price
        spread = _positive_decimal(self.spread, name="spread")
        if spread != expected_spread:
            raise ValueError("spread does not match order book")
        spread_bps = _positive_decimal(self.spread_bps, name="spread_bps")
        bid_depth = _non_negative_decimal(self.bid_depth_quote, name="bid_depth_quote")
        ask_depth = _non_negative_decimal(self.ask_depth_quote, name="ask_depth_quote")

        object.__setattr__(self, "source", source)
        object.__setattr__(self, "product_group", product_group)
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "spread", spread)
        object.__setattr__(self, "spread_bps", spread_bps)
        object.__setattr__(self, "bid_depth_quote", bid_depth)
        object.__setattr__(self, "ask_depth_quote", ask_depth)

    @property
    def executable_mid_price(self) -> Decimal:
        return (self.order_book.best_bid.price + self.order_book.best_ask.price) / Decimal("2")
