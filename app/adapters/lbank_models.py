from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


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


@dataclass(frozen=True)
class LBankMarketQuote:
    symbol: str
    last_price: Decimal
    marked_price: Decimal
    funding_rate: Decimal | None
    volume_24h: Decimal | None
    turnover_24h: Decimal | None


@dataclass(frozen=True)
class LBankBookLevel:
    price: Decimal
    volume: Decimal
    orders: int | None = None


@dataclass(frozen=True)
class LBankOrderBook:
    symbol: str
    bids: tuple[LBankBookLevel, ...]
    asks: tuple[LBankBookLevel, ...]

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

    @property
    def executable_mid_price(self) -> Decimal:
        return (self.order_book.best_bid.price + self.order_book.best_ask.price) / Decimal("2")
