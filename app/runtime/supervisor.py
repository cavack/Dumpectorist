import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from app.runtime.models import WorkerRunOutcome, WorkerRunStatus
from app.runtime.retention import RetentionResult
from app.runtime.scheduler import RuntimeOrchestrator
from app.runtime.telemetry import RuntimeAlert, RuntimeMetrics, RuntimeMetricsSnapshot


class RetentionCleaner(Protocol):
    async def cleanup(self, *, now: datetime) -> RetentionResult:
        """Remove expired runtime records."""


@dataclass(frozen=True)
class SupervisorCycle:
    observed_at: datetime
    outcomes: tuple[WorkerRunOutcome, ...]
    alerts: tuple[RuntimeAlert, ...]
    metrics: RuntimeMetricsSnapshot
    retention: RetentionResult | None = None

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")


class RuntimeSupervisor:
    def __init__(
        self,
        orchestrator: RuntimeOrchestrator,
        *,
        cleaner: RetentionCleaner | None = None,
        tick_seconds: float = 1.0,
        cleanup_interval_seconds: float = 3600.0,
        failure_alert_threshold: int = 3,
        metrics: RuntimeMetrics | None = None,
        clock: Callable[[], datetime] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        if tick_seconds <= 0:
            raise ValueError("tick_seconds must be positive")
        if cleanup_interval_seconds <= 0:
            raise ValueError("cleanup_interval_seconds must be positive")
        if failure_alert_threshold < 1:
            raise ValueError("failure_alert_threshold must be positive")

        self.orchestrator = orchestrator
        self.cleaner = cleaner
        self.tick_seconds = tick_seconds
        self.cleanup_interval_seconds = cleanup_interval_seconds
        self.failure_alert_threshold = failure_alert_threshold
        self.metrics = metrics or RuntimeMetrics()
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.logger = logger or logging.getLogger("dumpectorist.worker")
        self._next_cleanup_at: datetime | None = None

    async def run_cycle(self, *, now: datetime | None = None) -> SupervisorCycle:
        observed_at = now or self._aware_now()
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise ValueError("cycle time must be timezone-aware")

        outcomes = await self.orchestrator.run_due(observed_at)
        alerts = self.metrics.observe(
            outcomes,
            failure_alert_threshold=self.failure_alert_threshold,
        )
        self._log_outcomes(outcomes)
        self._log_alerts(alerts)

        retention: RetentionResult | None = None
        if self.cleaner is not None and self._cleanup_due(observed_at):
            try:
                retention = await self.cleaner.cleanup(now=observed_at)
                self.logger.info(
                    "runtime_retention_complete cutoff=%s deleted=%s",
                    retention.cutoff.isoformat(),
                    retention.deleted_records,
                )
            except Exception as error:
                self.logger.exception(
                    "runtime_retention_failed error=%s",
                    type(error).__name__,
                )
            finally:
                self._next_cleanup_at = observed_at + timedelta(
                    seconds=self.cleanup_interval_seconds
                )

        return SupervisorCycle(
            observed_at=observed_at,
            outcomes=outcomes,
            alerts=alerts,
            metrics=self.metrics.snapshot(now=observed_at),
            retention=retention,
        )

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            await self.run_cycle()
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=self.tick_seconds)
            except TimeoutError:
                continue

    def _cleanup_due(self, now: datetime) -> bool:
        return self._next_cleanup_at is None or now >= self._next_cleanup_at

    def _log_outcomes(self, outcomes: tuple[WorkerRunOutcome, ...]) -> None:
        for outcome in outcomes:
            level = (
                logging.ERROR
                if outcome.status
                in {
                    WorkerRunStatus.FAILED,
                    WorkerRunStatus.TIMED_OUT,
                    WorkerRunStatus.PERSISTENCE_FAILED,
                }
                else logging.WARNING
                if outcome.status == WorkerRunStatus.DEGRADED
                else logging.INFO
            )
            self.logger.log(
                level,
                "runtime_job_complete job=%s kind=%s status=%s duration_ms=%s message=%s",
                outcome.job_name,
                outcome.kind.value,
                outcome.status.value,
                outcome.duration_ms,
                outcome.message,
            )

    def _log_alerts(self, alerts: tuple[RuntimeAlert, ...]) -> None:
        for alert in alerts:
            self.logger.error(
                "runtime_failure_alert job=%s status=%s consecutive_failures=%s message=%s",
                alert.job_name,
                alert.status.value,
                alert.consecutive_failures,
                alert.message,
            )

    def _aware_now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("supervisor clock must return a timezone-aware datetime")
        return value
