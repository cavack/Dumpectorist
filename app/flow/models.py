from dataclasses import dataclass, field
from enum import StrEnum


class FlowStatus(StrEnum):
    READY = "READY"
    WAIT = "WAIT"
    INCOMPLETE = "INCOMPLETE"


@dataclass(frozen=True)
class FlowResult:
    symbol: str
    status: FlowStatus
    reasons: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_ready(self) -> bool:
        return self.status == FlowStatus.READY
