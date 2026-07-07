from dataclasses import dataclass, field
from enum import StrEnum


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


@dataclass(frozen=True)
class PlanRequest:
    symbol: str
    entry_value: float
    boundary_value: float
    multiplier: int = 1
    ratio: float = 2.0
