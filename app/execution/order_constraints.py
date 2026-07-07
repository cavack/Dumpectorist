from dataclasses import dataclass
from decimal import Decimal

from app.execution.liquidity_models import OrderSide, finite_decimal


@dataclass(frozen=True)
class ExecutionOrderRequest:
    side: OrderSide
    price: Decimal
    volume: Decimal
    post_only: bool = False

    def __post_init__(self):
        object.__setattr__(
            self,
            "price",
            finite_decimal(self.price, name="price", minimum=Decimal("0.00000001")),
        )
        object.__setattr__(
            self,
            "volume",
            finite_decimal(self.volume, name="volume", minimum=Decimal("0.00000001")),
        )

    @property
    def quote_cost(self):
        return self.price * self.volume


@dataclass(frozen=True)
class OrderConstraintValidation:
    valid: bool
    quote_cost: Decimal
    reasons: tuple[str, ...]
