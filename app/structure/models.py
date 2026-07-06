from dataclasses import dataclass, field
from enum import StrEnum


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


@dataclass(frozen=True)
class StructureSnapshot:
    symbol: str
    state: StructureState
    current_value: float
    reference_low: float
    reference_high: float
    reasons: tuple[str, ...] = field(default_factory=tuple)

    @property
    def needs_review(self) -> bool:
        return self.state in {StructureState.WEAK, StructureState.ALERT}
