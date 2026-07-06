from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class WatchStage(StrEnum):
    NEW = "NEW"
    WATCHING = "WATCHING"
    REVIEWING = "REVIEWING"
    PAUSED = "PAUSED"


@dataclass(frozen=True)
class WatchlistEntry:
    symbol: str
    stage: WatchStage
    source: str
    data: dict[str, Any]
    reasons: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_active(self) -> bool:
        return self.stage in {WatchStage.WATCHING, WatchStage.REVIEWING}
