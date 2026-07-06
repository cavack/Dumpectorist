from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class AdapterState(StrEnum):
    OK = "OK"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"


@dataclass(frozen=True)
class AdapterHealth:
    name: str
    state: AdapterState
    latency_ms: int | None = None
    message: str = ""

    @property
    def is_usable(self) -> bool:
        return self.state == AdapterState.OK


@dataclass(frozen=True)
class AdapterPayload:
    name: str
    data: dict[str, Any]
    health: AdapterHealth
