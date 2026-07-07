from dataclasses import dataclass, field
from enum import StrEnum

from app.core.numbers import positive_finite_float


class StructureState(StrEnum):
    NEUTRAL = "NEUTRAL"
    WEAK = "WEAK"
    ALERT = "ALERT"


@dataclass(frozen=True)
class StructureInput:
    symbol: str
    current_value: float
    reference_low: float
    reference_high: float

    def __post_init__(self) -> None:
        normalized_symbol = self.symbol.strip()
        if not normalized_symbol:
            raise ValueError("symbol is required")
        current_value = positive_finite_float(self.current_value, name="current_value")
        reference_low = positive_finite_float(self.reference_low, name="reference_low")
        reference_high = positive_finite_float(self.reference_high, name="reference_high")
        if reference_low >= reference_high:
            raise ValueError("reference_low must be below reference_high")
        object.__setattr__(self, "symbol", normalized_symbol)
        object.__setattr__(self, "current_value", current_value)
        object.__setattr__(self, "reference_low", reference_low)
        object.__setattr__(self, "reference_high", reference_high)


@dataclass(frozen=True)
class StructureSnapshot:
    symbol: str
    state: StructureState
    current_value: float
    reference_low: float
    reference_high: float
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        normalized_symbol = self.symbol.strip()
        if not normalized_symbol:
            raise ValueError("symbol is required")
        current_value = positive_finite_float(self.current_value, name="current_value")
        reference_low = positive_finite_float(self.reference_low, name="reference_low")
        reference_high = positive_finite_float(self.reference_high, name="reference_high")
        if reference_low >= reference_high:
            raise ValueError("reference_low must be below reference_high")
        object.__setattr__(self, "symbol", normalized_symbol)
        object.__setattr__(self, "current_value", current_value)
        object.__setattr__(self, "reference_low", reference_low)
        object.__setattr__(self, "reference_high", reference_high)

    @property
    def needs_review(self) -> bool:
        return self.state in {StructureState.WEAK, StructureState.ALERT}
