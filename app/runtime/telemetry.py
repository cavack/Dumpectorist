from dataclasses import dataclass, field
from datetime import datetime

from app.runtime.models import WorkerRunOutcome, WorkerRunStatus


FAILURE_STATUSES = {
    WorkerRunStatus.FAILED,
    WorkerRunStatus.TIMED_OUT,
    WorkerRunStatus.PERSISTENCE_FAILED,
}


@dataclass(frozen=True)
class RuntimeAlert:
    job_name: str
    status: WorkerRunStatus
    consecutive_failures: int
    message: str

    def __post_init__(self) -> None:
        if not self.job_name.strip():
            raise ValueError("alert job_name is required")
        if self.consecutive_failures < 1:
            raise ValueError("consecutive_failures must be positive")


@dataclass(frozen=True)
class RuntimeMetricsSnapshot:
    observed_at: datetime
    total_runs: int
    status_counts: dict[str, int]
    consecutive_failures: dict[str, int]
    last_status: dict[str, str]

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        if self.total_runs < 0:
            raise ValueError("total_runs must be non-negative")


@dataclass
class RuntimeMetrics:
    total_runs: int = 0
    status_counts: dict[WorkerRunStatus, int] = field(default_factory=dict)
    consecutive_failures: dict[str, int] = field(default_factory=dict)
    last_status: dict[str, WorkerRunStatus] = field(default_factory=dict)
    _last_alerted_failure_count: dict[str, int] = field(default_factory=dict)

    def observe(
        self,
        outcomes: tuple[WorkerRunOutcome, ...],
        *,
        failure_alert_threshold: int,
    ) -> tuple[RuntimeAlert, ...]:
        if failure_alert_threshold < 1:
            raise ValueError("failure_alert_threshold must be positive")

        alerts: list[RuntimeAlert] = []
        for outcome in outcomes:
            self.total_runs += 1
            self.status_counts[outcome.status] = self.status_counts.get(outcome.status, 0) + 1
            self.last_status[outcome.job_name] = outcome.status

            if outcome.status in FAILURE_STATUSES:
                failure_count = self.consecutive_failures.get(outcome.job_name, 0) + 1
                self.consecutive_failures[outcome.job_name] = failure_count
                last_alerted = self._last_alerted_failure_count.get(outcome.job_name, 0)
                if failure_count >= failure_alert_threshold and failure_count > last_alerted:
                    alerts.append(
                        RuntimeAlert(
                            job_name=outcome.job_name,
                            status=outcome.status,
                            consecutive_failures=failure_count,
                            message=outcome.message,
                        )
                    )
                    self._last_alerted_failure_count[outcome.job_name] = failure_count
            else:
                self.consecutive_failures[outcome.job_name] = 0
                self._last_alerted_failure_count.pop(outcome.job_name, None)

        return tuple(alerts)

    def snapshot(self, *, now: datetime) -> RuntimeMetricsSnapshot:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        return RuntimeMetricsSnapshot(
            observed_at=now,
            total_runs=self.total_runs,
            status_counts={status.value: count for status, count in self.status_counts.items()},
            consecutive_failures=dict(self.consecutive_failures),
            last_status={name: status.value for name, status in self.last_status.items()},
        )
