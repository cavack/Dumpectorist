from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class LifecycleState(StrEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    CLOSED = "CLOSED"


@dataclass(frozen=True)
class LifecycleRecord:
    symbol: str
    state: LifecycleState
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    closed_at: datetime | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_terminal(self) -> bool:
        return self.state in {LifecycleState.EXPIRED, LifecycleState.CLOSED}
