from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from app.adapters.models import AdapterPayload, AdapterState


class SourceJobKind(StrEnum):
    EXECUTION = "EXECUTION"
    BENCHMARK = "BENCHMARK"
    STRUCTURE = "STRUCTURE"
    DISCOVERY = "DISCOVERY"


class WorkerRunStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    PERSISTENCE_FAILED = "PERSISTENCE_FAILED"


class SourceAdapter(Protocol):
    name: str

    async def load(self) -> AdapterPayload:
        """Load one public source payload without placing orders."""


@dataclass(frozen=True)
class RuntimeSchedule:
    interval_seconds: float
    timeout_seconds: float
    initial_delay_seconds: float = 0.0

    def __post_init__(self) -> None:
        if self.interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.initial_delay_seconds < 0:
            raise ValueError("initial_delay_seconds must be non-negative")


@dataclass(frozen=True)
class ScheduledSourceJob:
    name: str
    kind: SourceJobKind
    adapter: SourceAdapter
    schedule: RuntimeSchedule

    def __post_init__(self) -> None:
        normalized_name = self.name.strip()
        if not normalized_name:
            raise ValueError("job name is required")
        adapter_name = self.adapter.name.strip()
        if not adapter_name:
            raise ValueError("adapter name is required")
        object.__setattr__(self, "name", normalized_name)


@dataclass(frozen=True)
class WorkerRunOutcome:
    job_name: str
    kind: SourceJobKind
    status: WorkerRunStatus
    started_at: datetime
    finished_at: datetime
    adapter_state: AdapterState | None = None
    message: str = ""

    def __post_init__(self) -> None:
        if not self.job_name.strip():
            raise ValueError("job_name is required")
        for value, field_name in (
            (self.started_at, "started_at"),
            (self.finished_at, "finished_at"),
        ):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{field_name} must be timezone-aware")
        if self.finished_at < self.started_at:
            raise ValueError("finished_at must not precede started_at")

    @property
    def duration_ms(self) -> int:
        return round((self.finished_at - self.started_at).total_seconds() * 1000)

    @property
    def completed_without_failure(self) -> bool:
        return self.status in {
            WorkerRunStatus.SUCCEEDED,
            WorkerRunStatus.DEGRADED,
        }
