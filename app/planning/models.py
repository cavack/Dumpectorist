from dataclasses import dataclass, field
from enum import StrEnum

from app.core.numbers import finite_float, positive_finite_float


class PlanStatus(StrEnum):
    HOLD = "HOLD"
    READY = "READY"


@dataclass(frozen=True)
class PlanDraft:
    symbol: str
    status: PlanStatus
    entry_value: float | None = None
    boundary_value: float | None = None
    objective_value: float | None = None
    multiplier: int = 1
    ratio: float = 2.0
    notes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        normalized_symbol = self.symbol.strip()
        if not normalized_symbol:
            raise ValueError("symbol is required")
        if isinstance(self.multiplier, bool) or not isinstance(self.multiplier, int):
            raise ValueError("multiplier must be an integer")
        if self.multiplier < 1 or self.multiplier > 5:
            raise ValueError("multiplier must be between 1 and 5")
        ratio = finite_float(self.ratio, name="ratio")

        normalized_values: dict[str, float | None] = {}
        for name, value in (
            ("entry_value", self.entry_value),
            ("boundary_value", self.boundary_value),
            ("objective_value", self.objective_value),
        ):
            normalized_values[name] = (
                finite_float(value, name=name) if value is not None else None
            )

        complete_values = all(value is not None for value in normalized_values.values())
        if complete_values:
            entry = normalized_values["entry_value"]
            boundary = normalized_values["boundary_value"]
            objective = normalized_values["objective_value"]
            if not 0 < objective < entry < boundary:
                raise ValueError("short plan must satisfy objective < entry < boundary")

        object.__setattr__(self, "symbol", normalized_symbol)
        object.__setattr__(self, "ratio", ratio)
        for name, value in normalized_values.items():
            object.__setattr__(self, name, value)


@dataclass(frozen=True)
class PlanRequest:
    symbol: str
    entry_value: float
    boundary_value: float
    multiplier: int = 1
    ratio: float = 2.0

    def __post_init__(self) -> None:
        normalized_symbol = self.symbol.strip()
        if not normalized_symbol:
            raise ValueError("symbol is required")
        entry = finite_float(self.entry_value, name="entry_value")
        boundary = finite_float(self.boundary_value, name="boundary_value")
        ratio = finite_float(self.ratio, name="ratio")
        if isinstance(self.multiplier, bool) or not isinstance(self.multiplier, int):
            raise ValueError("multiplier must be an integer")
        object.__setattr__(self, "symbol", normalized_symbol)
        object.__setattr__(self, "entry_value", entry)
        object.__setattr__(self, "boundary_value", boundary)
        object.__setattr__(self, "ratio", ratio)
