from dataclasses import dataclass
from decimal import Decimal

from app.adapters.lbank_models import LBankInstrument
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


def validate_order_constraints(request, instrument: LBankInstrument):
    reasons = []
    if request.price % instrument.price_tick:
        reasons.append("PRICE_NOT_ALIGNED_TO_TICK")
    if request.volume % instrument.volume_tick:
        reasons.append("VOLUME_NOT_ALIGNED_TO_TICK")
    if instrument.min_order_volume is None:
        reasons.append("MIN_ORDER_VOLUME_UNAVAILABLE")
    elif request.volume < instrument.min_order_volume:
        reasons.append("ORDER_VOLUME_BELOW_MINIMUM")
    if instrument.min_order_cost is None:
        reasons.append("MIN_ORDER_COST_UNAVAILABLE")
    elif request.quote_cost < instrument.min_order_cost:
        reasons.append("ORDER_COST_BELOW_MINIMUM")
    return OrderConstraintValidation(
        valid=not reasons,
        quote_cost=request.quote_cost,
        reasons=tuple(reasons),
    )
