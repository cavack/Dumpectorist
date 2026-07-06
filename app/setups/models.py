from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class SetupLabel(StrEnum):
    IGNORE = "IGNORE"
    WATCH = "WATCH"
    REVIEW = "REVIEW"


@dataclass(frozen=True)
class SetupCandidate:
    symbol: str
    label: SetupLabel
    source_state: str
    data: dict[str, Any]
    reasons: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_actionable(self) -> bool:
        return self.label == SetupLabel.REVIEW
