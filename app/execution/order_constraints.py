from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class OrderConstraintValidation:
    valid: bool
    quote_cost: Decimal
    reasons: tuple[str, ...]
